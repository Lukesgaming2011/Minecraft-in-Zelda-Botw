"""BOTW host endpoint for SkyCraft protocol 12 and the HyruleCraft renderer.

Reads the signature-gated test Cemu; input ownership writes only our mod mailbox.
Minecraft remains held until a real BOTW collision exporter is connected.
"""
import argparse
import ctypes
import importlib.util
import json
import math
import mmap
import os
from pathlib import Path
import struct
import sys
import time
import zlib
from movement import MovementAuthority
from movement_completion import completion
from mouse_look import MouseLook
from direct_mouse import DirectMouse, DirectMouseProbe
from runtime_config import native_directory, mouse_scale
from camera_projection import read_projection
from scripted_movement import ScriptedMovement
from scripted_placement import ScriptedPlacement

NAME = r'Local\HyruleCraft_v1'
COL = 0x20000
PIX = COL + (32 << 20)
SLOT = 3840 * 2160 * 4
RENDER = PIX + SLOT * 3
SIZE = RENDER + (64 << 20)
ROOT = Path(__file__).resolve().parent


def look(direction):
    x, y, z = direction
    return -math.degrees(math.atan2(x, z)), -math.degrees(math.asin(max(-1, min(1, y))))


def read_seqlock(memory, offset, length):
    for _ in range(8):
        first = struct.unpack_from('<I', memory, offset)[0]
        if first & 1:
            continue
        raw = memory[offset:offset + length]
        if first == struct.unpack_from('<I', memory, offset)[0]:
            return raw
    return None


class Link:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetTickCount64.restype = ctypes.c_uint64
        # InterlockedExchange is a compiler intrinsic, not a kernel32 export on this Windows.
        # Windows x64 leaf function: mov eax,edx; xchg [rcx],eax; ret.
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError('The protocol probe requires 64-bit Python')
        self.kernel.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        self.kernel.VirtualAlloc.restype = ctypes.c_void_p
        self.kernel.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        self.kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        self.atomic_code = self.kernel.VirtualAlloc(None, 4096, 0x3000, 4)
        if not self.atomic_code:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(self.atomic_code, b'\x8b\xc2\x87\x01\xc3', 5)
        ctypes.memmove(self.atomic_code+16,b'\xf0\x09\x11\xc3',4)  # lock or [rcx],edx
        ctypes.memmove(self.atomic_code+32,b'\xf0\x21\x11\xc3',4)  # lock and [rcx],edx
        ctypes.memmove(self.atomic_code+48,b'\xf0\x01\x11\xc3',4)  # lock add [rcx],edx
        old_protect = ctypes.c_uint32()
        if not self.kernel.VirtualProtect(self.atomic_code, 4096, 0x20, ctypes.byref(old_protect)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.kernel.FlushInstructionCache.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        self.kernel.FlushInstructionCache(ctypes.c_void_p(-1), self.atomic_code, 52)
        self.exchange = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(ctypes.c_long), ctypes.c_long)(self.atomic_code)
        atomic_type=ctypes.WINFUNCTYPE(None,ctypes.POINTER(ctypes.c_long),ctypes.c_uint32)
        self.atomic_or=atomic_type(self.atomic_code+16)
        self.atomic_and=atomic_type(self.atomic_code+32)
        self.atomic_add=atomic_type(self.atomic_code+48)
        self.memory = mmap.mmap(-1, SIZE, tagname=NAME)
        # Only one host may initialize this endpoint. A named mutex prevents resets.
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.mutex = self.kernel.CreateMutexW(None, False, NAME + '_host')
        if not self.mutex or ctypes.get_last_error() == 183:
            self.memory.close()
            if self.mutex:
                self.kernel.CloseHandle(self.mutex)
            raise RuntimeError('HyruleCraft host is already running')
        old_magic, old_version, _, old_mc_pid = struct.unpack_from('<IIII', self.memory, 0)
        old_mc_pid = old_mc_pid if (old_magic, old_version) == (0x43594B53, 12) else 0
        self.memory[:] = bytes(SIZE)
        struct.pack_into('<IIII', self.memory, 0, 0x43594B53, 12, os.getpid(), old_mc_pid)
        # SkyCraft's water field must use its explicit no-water sentinel.
        struct.pack_into('<256f', self.memory, 0x410, *([-1e30] * 256))
        self.seq = 0
        self.front = 2
        self.render_counts = {}
        self.overlay_frames = 0

    def publish(self, position, direction, teleport, width=1280, height=720, eye=None, fov=50., projection=None, gameplay_direction=None):
        yaw, pitch = look(gameplay_direction or direction)
        self.seq += 2
        struct.pack_into('<I', self.memory, 0x100, self.seq - 1)
        struct.pack_into('<IIIdddffIIIf', self.memory, 0x104,
                         1, 1, 1, *position, yaw, pitch, teleport, width, height, 12.)
        struct.pack_into('<I', self.memory, 0x100, self.seq)
        struct.pack_into('<Q', self.memory, 0x10, self.kernel.GetTickCount64())
        struct.pack_into('<I', self.memory, 0xc00, self.seq-1)
        struct.pack_into('<Idddffff', self.memory, 0xc04, 0x41434348, *(eye or position), *direction, fov)
        struct.pack_into('<fffI', self.memory, 0xc30,
                         projection['near'] if projection else 0.,
                         projection['far'] if projection else 0.,
                         projection['aspect'] if projection else 0., int(projection is not None))
        struct.pack_into('<I', self.memory, 0xc00, self.seq)

    def mc(self):
        raw = read_seqlock(self.memory, 0x200, 0xc8)
        if raw is None:
            return None
        data = struct.unpack_from('<IIdddffffIIQfffIddd', raw)
        cam_mode = struct.unpack_from('<I', raw, 0xc0)[0] if len(raw) >= 0xc4 else 0
        cam_dist = struct.unpack_from('<f', raw, 0xc4)[0] if len(raw) >= 0xc8 else 0.0
        return dict(pid=struct.unpack_from('<I', self.memory, 12)[0], flags=data[1],
                    position=data[2:5], yaw=data[5], pitch=data[6], sensitivity=data[8], teleport_ack=data[9],
                    frame=data[11], fov=data[12], camera_mode=cam_mode, camera_distance=cam_dist)

    def drain_render(self):
        capacity = (64 << 20) - 0x80
        head = struct.unpack_from('<Q', self.memory, RENDER)[0]
        tail = struct.unpack_from('<Q', self.memory, RENDER + 0x40)[0]
        if head < tail or head - tail > capacity:
            raise RuntimeError('Invalid Minecraft render ring counters')
        while tail < head:
            pos = tail % capacity
            if capacity - pos < 8:
                tail += capacity - pos
                continue
            kind, length = struct.unpack_from('<II', self.memory, RENDER + 0x80 + pos)
            if kind == 0:
                tail += capacity - pos
                continue
            step = (8 + length + 7) & ~7
            if step > capacity - pos or step > head - tail:
                raise RuntimeError('Invalid Minecraft render message length')
            self.render_counts[kind] = self.render_counts.get(kind, 0) + 1
            # Probe acknowledges exports; a future Cemu renderer must consume payloads here.
            tail += step
        struct.pack_into('<Q', self.memory, RENDER + 0x40, tail)
        event_head = struct.unpack_from('<Q', self.memory, 0x17000)[0]
        struct.pack_into('<Q', self.memory, 0x17040, event_head)

    def overlay(self):
        state = struct.unpack_from('<I', self.memory, 0x300)[0]
        if not state & 4:
            return None
        # Protocol triple-buffer ownership exchange must be atomic with the Java producer.
        cell = ctypes.c_long.from_buffer(self.memory, 0x300)
        old = self.exchange(ctypes.byref(cell), self.front)
        del cell
        self.front = old & 3
        if self.front >= 3:
            raise RuntimeError('Invalid overlay slot')
        width, height, flags = struct.unpack_from('<III', self.memory, 0x340 + self.front * 0x40)
        if not (0 < width <= 3840 and 0 < height <= 2160):
            return None
        start = PIX + self.front * SLOT
        self.overlay_frames += 1
        return width, height, flags, self.memory[start:start + width * height * 4]

    def event(self, kind, code, a=0, b=0, c=0):
        head = struct.unpack_from('<Q', self.memory, 0x1000)[0]
        tail = struct.unpack_from('<Q', self.memory, 0x1040)[0]
        if not 0 <= head-tail < 4096: raise RuntimeError('Invalid or full Minecraft input ring')
        struct.pack_into('<HHiii',self.memory,0x1080+(head%4096)*16,kind,code,a,b,c)
        struct.pack_into('<Q',self.memory,0x1000,head+1)

    def key(self, scancode, down):
        head = struct.unpack_from('<Q', self.memory, 0x1000)[0]
        tail = struct.unpack_from('<Q', self.memory, 0x1040)[0]
        if head - tail >= 4096:
            raise RuntimeError('Minecraft input ring is full')
        struct.pack_into('<HHiii', self.memory, 0x1080 + (head % 4096) * 16,
                         1, scancode, int(down), 0, 0)
        struct.pack_into('<Q', self.memory, 0x1000, head + 1)

    def close(self):
        struct.pack_into('<Q', self.memory, 0x10, 0)
        self.memory.close()
        self.kernel.CloseHandle(self.mutex)
        self.kernel.VirtualFree(self.atomic_code, 0, 0x8000)


def save_png(path, frame):
    width, height, flags, rgba = frame
    rows = [rgba[i * width * 4:(i + 1) * width * 4] for i in range(height)]
    if flags & 1:
        rows.reverse()
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(b''.join(b'\0' + row for row in rows))) + chunk(b'IEND', b'')
    path.write_bytes(data)


class MouseCapture:
    """Own game input: suppress only this lab's MC button events before Cemu sees them."""
    def __init__(self,link,pid):
        from ctypes import wintypes as W
        self.link,self.pid=link,pid
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.GetForegroundWindow.restype=W.HWND
        self.user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,W.WPARAM,W.LPARAM)
        self.user.SetWindowsHookExW.argtypes=[ctypes.c_int,callback_type,W.HINSTANCE,W.DWORD]
        self.user.SetWindowsHookExW.restype=W.HANDLE
        self.user.CallNextHookEx.argtypes=[W.HANDLE,ctypes.c_int,W.WPARAM,W.LPARAM]
        self.user.CallNextHookEx.restype=ctypes.c_ssize_t
        self.user.UnhookWindowsHookEx.argtypes=[W.HANDLE]
        self.user.PeekMessageW.argtypes=[ctypes.POINTER(W.MSG),W.HWND,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32]
        self.user.TranslateMessage.argtypes=[ctypes.POINTER(W.MSG)]
        self.user.DispatchMessageW.argtypes=[ctypes.POINTER(W.MSG)]
        self.message=W.MSG()
        self.user.GetAsyncKeyState.argtypes=[ctypes.c_int]
        self.user.GetAsyncKeyState.restype=ctypes.c_short
        self.user.GetCursorPos.argtypes=[ctypes.POINTER(W.POINT)]
        self.user.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
        self.mouse_locked=False
        self.mouse_center=None
        self.cursor_failures=0
        self.warp_failures=0
        messages={0x201:(1,True),0x202:(1,False),0x204:(2,True),0x205:(2,False),0x207:(4,True),0x208:(4,False)}
        def receive(code,message,data):
            now = link.kernel.GetTickCount64()
            host_beat = struct.unpack_from('<Q',link.memory,0x10)[0]
            renderer_beat = struct.unpack_from('<Q',link.memory,0xc60)[0]
            lease_valid = 0 <= now-host_beat <= 500 and 0 <= now-renderer_beat <= 500
            if code>=0 and message in messages and lease_valid and struct.unpack_from('<I',link.memory,0xc48)[0]:
                foreground_pid=W.DWORD()
                self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),ctypes.byref(foreground_pid))
                if foreground_pid.value==pid:
                    mask,down=messages[message]
                    cell=ctypes.c_long.from_buffer(link.memory,0xc5c)
                    if down:
                        link.atomic_or(ctypes.byref(cell),mask|(mask<<8))
                    else:
                        link.atomic_and(ctypes.byref(cell),(~mask)&0xffffffff)
                    del cell
                    return 1
            return self.user.CallNextHookEx(None,code,message,data)
        self.callback=callback_type(receive)
        self.hook=self.user.SetWindowsHookExW(14,self.callback,None,0)
        if not self.hook:
            raise ctypes.WinError(ctypes.get_last_error())
    def pump(self):
        while self.user.PeekMessageW(ctypes.byref(self.message),None,0,0,1):
            self.user.TranslateMessage(ctypes.byref(self.message))
            self.user.DispatchMessageW(ctypes.byref(self.message))
    def poll_physical(self):
        # This process has no ReShade hooks. Only the renderer writes MC events.
        from ctypes import wintypes as W
        foreground_pid=W.DWORD()
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),ctypes.byref(foreground_pid))
        mem=self.link.memory
        allowed=foreground_pid.value==self.pid and bool(struct.unpack_from('<I',mem,0xc68)[0])
        mem[0xd00:0xe00]=bytes(int(bool(self.user.GetAsyncKeyState(vk)&0x8000)) for vk in range(256)) if allowed else bytes(256)
        now=self.link.kernel.GetTickCount64()
        renderer_beat=struct.unpack_from('<Q',mem,0xc60)[0]
        mc=self.link.mc()
        desktop_chord=any(mem[0xd00+vk] for vk in (0x12,0xa4,0x5b,0x5c))
        if not allowed or desktop_chord:
            for offset in (0xc54,0xc58,0xc5c):struct.pack_into('<I',mem,offset,0)
        enabled=allowed and not desktop_chord and bool(struct.unpack_from('<I',mem,0xc48)[0]) and 0<=now-renderer_beat<=500 and mc and mc['flags']&1
        status=0
        if enabled:
            cursor=W.POINT()
            if self.user.GetCursorPos(ctypes.byref(cursor)):
                status=1
                struct.pack_into('<ii',mem,0xccc,cursor.x,cursor.y)
                center=struct.unpack_from('<ii',mem,0xcb0)
                screen=bool(mc['flags']&2)
                if not screen and center!=(0,0):
                    if self.mouse_locked and center==self.mouse_center:
                        dx=max(-1000,min(1000,cursor.x-center[0]))
                        dy=max(-1000,min(1000,cursor.y-center[1]))
                        for offset,total,delta in ((0xc54,0xcc0,dx),(0xc58,0xcc4,dy)):
                            if delta:
                                cell=ctypes.c_long.from_buffer(mem,offset)
                                self.link.atomic_add(ctypes.byref(cell),delta)
                                del cell
                                value=struct.unpack_from('<I',mem,total)[0]
                                struct.pack_into('<I',mem,total,(value+abs(delta))&0xffffffff)
                    self.mouse_locked=bool(self.user.SetCursorPos(*center))
                    self.mouse_center=center
                    if self.mouse_locked:status|=2
                    else:self.warp_failures+=1
                else:self.mouse_locked=False
            else:
                self.cursor_failures+=1;self.mouse_locked=False
        else:self.mouse_locked=False
        struct.pack_into('<I',mem,0xcc8,status)
        struct.pack_into('<II',mem,0xca0,self.cursor_failures,self.warp_failures)
    def close(self):
        self.link.memory[0xd00:0xe00]=bytes(256)
        struct.pack_into('<I',self.link.memory,0xcc8,0)
        self.user.UnhookWindowsHookEx(self.hook)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-directory',type=Path,default=native_directory(ROOT))
    parser.add_argument('--mouse-scale',type=mouse_scale,default=.5)
    parser.add_argument('--invert-y',action='store_true')
    parser.add_argument('--fullscreen',action='store_true')
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--cemu-log', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--inventory-probe', action='store_true')
    parser.add_argument('--renderer', action='store_true', help='Give the ReShade addon sole ownership of render/overlay rings')
    parser.add_argument('--first-person', action='store_true', help='Enable the existing verified BOTW first-person patch')
    parser.add_argument('--no-input', action='store_true', help='Disable mouse hook and native F7 capture for observation tests')
    parser.add_argument('--recover-home',action='store_true',help='Return once to verified clear nearby ground')
    parser.add_argument('--mouse-stop-probe',action='store_true',help='Bounded native camera neutral-input check; requires --no-input')
    parser.add_argument('--mc-movement', action='store_true', help='Experimental: let collision-ready MC physics drive bounded Link corrections')
    parser.add_argument('--terrain-ground-anchor',type=float,nargs=3,help='Previously verified native ground point for a bridge-only restart while standing on MC blocks')
    parser.add_argument('--experimental-heightfield', type=Path, help='Limited ground test: local Terrain/A directory; no object/bridge/cave collision')
    parser.add_argument('--scripted-movement-probe', action='store_true', help='Bounded foreground-only development test; direct MC events, no OS capture')
    parser.add_argument('--probe-ready-timeout', type=float, default=45, help='Bounded wait for dev fixture and foreground readiness; action duration remains 8s')
    parser.add_argument('--scripted-support-seconds', type=float, default=2, help='Measured stand duration, 2 to 5 seconds within the 8s probe bound')
    parser.add_argument('--scripted-placement-probe', action='store_true', help='Bounded native aim and one direct MC right click; physical capture disabled')
    parser.add_argument('--scripted-placement-turn-degrees', type=float, default=35, help='Bounded placement camera turn, 1 to 90 degrees')
    parser.add_argument('--scripted-movement-target', nargs=3, type=int, help='Verify and walk to an existing server oak block; never create a fixture')
    parser.add_argument('--scripted-jump-on-target', action='store_true', help='Jump on the verified block, land, then measure sustained support')
    parser.add_argument('--scripted-controls-probe', action='store_true', help='Bounded keyboard movement validation with physical input disabled')
    parser.add_argument('--scripted-travel-probe',action='store_true',help='Bounded 32m travel validation; physical input disabled')
    args = parser.parse_args()
    if args.scripted_travel_probe:
        if not args.no_input:parser.error('Travel validation requires --no-input')
        args.scripted_controls_probe=True
    if args.mouse_stop_probe and not args.no_input:parser.error('Mouse stop probe requires --no-input')
    if args.scripted_controls_probe and (args.scripted_movement_probe or args.scripted_placement_probe or not (args.no_input and args.renderer and args.mc_movement and args.experimental_heightfield)):
        parser.error('Controls probe requires no-input, renderer, movement and terrain, without another probe')
    if args.scripted_jump_on_target and not args.scripted_movement_probe: parser.error('Target jump requires scripted-movement-probe')
    if args.scripted_movement_target and not args.scripted_movement_probe: parser.error('An existing target requires scripted-movement-probe')
    if not 1 <= args.scripted_placement_turn_degrees <= 90: parser.error('Placement turn must be 1 to 90 degrees')
    if args.scripted_placement_probe and (args.scripted_movement_probe or not (args.no_input and args.renderer and args.mc_movement and args.experimental_heightfield)):
        parser.error('Placement probe requires no-input, renderer, mc-movement and heightfields, without movement probe')
    if not 2 <= args.scripted_support_seconds <= 5:
        parser.error('Measured support duration must be 2 to 5 seconds')
    if not 1 <= args.probe_ready_timeout <= 600:
        parser.error('Probe readiness timeout must be between 1 and 600 seconds')
    if args.scripted_movement_probe and not (args.no_input and args.mc_movement and args.experimental_heightfield and args.renderer):
        parser.error('Scripted probe requires no-input, renderer, mc-movement and authentic heightfields')
    if args.mc_movement and not args.renderer:
        parser.error('--mc-movement requires --renderer')
    # Reuse our own already-validated, signature-gated BOTW reader; never call its write methods.
    sys.path.insert(0, str(args.native_directory))
    spec = importlib.util.spec_from_file_location('botw_reader', args.native_directory / 'bridge.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    process = reader.Process(args.pid, args.cemu_log)
    if args.first_person:
        process.set(0x1b4,1)
    link = Link()
    struct.pack_into('<I',link.memory,0xce0,1 if args.fullscreen else 2)
    struct.pack_into('<I',link.memory,0xc68,int(args.renderer and not args.no_input))
    capture=MouseCapture(link,args.pid) if args.renderer and not args.no_input else None
    authority = MovementAuthority()
    pending_move_since = None
    movement_error = None
    movement_retry_until = 0.
    movement_stalls = 0
    placement = ScriptedPlacement(args.scripted_placement_turn_degrees) if args.scripted_placement_probe else None
    placement_reported = False
    placement_stick = (0.,0.)
    probe = None
    if args.scripted_controls_probe:
        from scripted_controls import ScriptedControls
        if args.scripted_travel_probe:from scripted_travel import TravelProbe as ScriptedControls
    controls = None
    controls_ready_since = None
    controls_keys = set()
    probe_keys = set()
    probe_wait_since = time.monotonic()
    existing_aim_since = None
    movement_aim_x = 0.
    probe_ready_since = None
    if args.scripted_movement_target: struct.pack_into('<iii',link.memory,0xc98,*args.scripted_movement_target)
    struct.pack_into('<I',link.memory,0xc6c,4 if args.scripted_controls_probe else 3 if args.scripted_movement_target else 2 if args.scripted_placement_probe else int(args.scripted_movement_probe))
    terrain_report = None
    terrain_loader = None
    start = time.monotonic()
    last_report = 0
    inventory_opened = False
    world_ready_since = None
    hud_saved = False
    teleport = 1
    initial = None
    mouse_look = MouseLook()
    from mouse_stop_probe import MouseStopProbe
    mouse_probe=DirectMouseProbe() if args.mouse_stop_probe else None
    current_fp_mode = 1 if args.first_person else 0
    last_gameplay_direction = None
    try:
        direct_mouse=DirectMouse(scale=args.mouse_scale,invert_y=args.invert_y)
        direct_seq=0
        recover_requested=args.recover_home
        recover_pending=None
        recover_key_down=False
        while time.monotonic() - start < args.seconds:
            if not process.is_running():
                print('Test Cemu exited; releasing Minecraft input and stopping bridge.', flush=True)
                break
            if capture:
                capture.pump()
                capture.poll_physical()
            try:
                position = process.position()
                eye, direction = process.view()
                projection = read_projection(process)
            except (ValueError, OSError):
                # Title screens, loading and event cameras are not gameplay frames.
                # Native camera structures are updated concurrently. A single
                # rejected snapshot must not manufacture a disconnect. Leave the
                # last valid heartbeat to expire normally (500ms); no invalid
                # pose is published, and input releases immediately.
                struct.pack_into('<I', link.memory, 0xc48, 0)
                mouse_look.reset()
                if args.renderer:
                    # A rejected camera snapshot must not leave the last turn held.
                    process.put(0x48,struct.pack('>ffff',0.,0.,0.,0.))
                    process.set(0x3c,0)
                    process.set(0x198,int(not args.no_input))
                    for off in (0xc54,0xc58):
                        cell=ctypes.c_long.from_buffer(link.memory,off)
                        link.exchange(ctypes.byref(cell),0)
                        del cell
                time.sleep(0.01)
                continue
            recover_key=bool(capture and link.memory[0xd00+0x77] and struct.unpack_from('<I',link.memory,0xc48)[0])
            recover_requested=recover_requested or (recover_key and not recover_key_down)
            recover_key_down=recover_key
            if recover_pending is not None:
                command=process.get(0x10)
                if not command and process.get(0x14,'i')==2:
                    initial=position;teleport+=1;authority=MovementAuthority();pending_move_since=None
                    recovery_report=dict(passed=math.dist(position,recover_point)<.05,target=recover_point,native=position,physical_capture=not args.no_input)
                    (ROOT/'recovery-validation.json').write_text(json.dumps(recovery_report,indent=2))
                    recover_pending=None
                elif time.monotonic()-recover_pending>2:
                    if command==4:process.set(0x10,0)
                    recover_pending=None
                    (ROOT/'recovery-validation.json').write_text(json.dumps(dict(passed=False,reason='Native recovery acknowledgement timed out'),indent=2))
                    print('Home recovery was not acknowledged; movement left released.',flush=True)
                else:
                    time.sleep(1/60);continue
            if recover_requested:
                recover_requested=False
                from ground_validation import load_anchor
                recover_point=load_anchor(ROOT/'terrain-ground-validation.json',args.experimental_heightfield,position)
                if recover_point is None:
                    print('No verified nearby home calibration; recovery refused.',flush=True)
                else:
                    link.event(6,0)
                    if pending_move_since is not None and process.get(0x10)==3:process.set(0x10,0)
                    pending_move_since=None
                    if process.recover_home(recover_point):
                        recover_pending=time.monotonic();time.sleep(1/60);continue
            if initial is None:
                initial = position
            if args.experimental_heightfield:
                if terrain_loader is None:
                    from dynamic_terrain import DynamicTerrain
                    from collaboration.terrain_export import CollisionRingWriter
                    from ground_validation import load_anchor
                    ground_anchor=args.terrain_ground_anchor or load_anchor(ROOT/'terrain-ground-validation.json',args.experimental_heightfield,position)
                    terrain_loader = DynamicTerrain(args.experimental_heightfield, CollisionRingWriter(link.memory),ground_anchor=ground_anchor)
                # Preparation runs off the heartbeat thread. Only this host writes
                # collision packets, retaining old regions and retrying backpressure.
                from travel_prefetch import position_for_terrain
                terrain_position=position_for_terrain(position,link.mc(),
                    now_ms=link.kernel.GetTickCount64(),heartbeat=struct.unpack_from('<Q',link.memory,0x18)[0],
                    teleport=teleport,anchor=authority.hold_position,anchor_epoch=authority.hold_teleport)
                terrain_report = terrain_loader.tick(terrain_position)
                if not getattr(terrain_loader,'saved_ground_validation',False):
                    from ground_validation import save_anchor
                    terrain_loader.saved_ground_validation=save_anchor(ROOT/'terrain-ground-validation.json',args.experimental_heightfield,terrain_report)
            mc = link.mc()
            enabled = bool(struct.unpack_from('<I',link.memory,0xc48)[0])
            probe_grant = (args.scripted_movement_probe or (args.scripted_controls_probe and (controls is None or not controls.finished)) or (placement is not None and not placement.finished)) and struct.unpack_from('<I',link.memory,0xc70)[0]==1 and (probe is None or not probe.finished)
            point = authority.target(enabled=args.mc_movement and (enabled or probe_grant) and movement_error is None,
                now_ms=link.kernel.GetTickCount64(),
                mc_heartbeat=struct.unpack_from('<Q',link.memory,0x18)[0],
                renderer_heartbeat=struct.unpack_from('<Q',link.memory,0xc60)[0],
                mc=mc, teleport=teleport, position=position, now=time.monotonic())
            if not authority.active and args.mc_movement and movement_error is None and (not args.no_input or probe_grant):
                point=authority.hold_target(now_ms=link.kernel.GetTickCount64(),
                    mc_heartbeat=struct.unpack_from('<Q',link.memory,0x18)[0],
                    renderer_heartbeat=struct.unpack_from('<Q',link.memory,0xc60)[0],
                    mc=mc,teleport=teleport,position=position)
            movement_aim_x = 0.
            existing_aim_ready = True
            if args.scripted_movement_target and probe is None and authority.active:
                bx,by,bz=args.scripted_movement_target
                desired=-math.degrees(math.atan2(bx+.5-mc['position'][0],bz+.5-mc['position'][2]))
                delta=(desired-mc['yaw']+180)%360-180
                existing_aim_ready=abs(delta)<=4
                existing_aim_since=existing_aim_since or time.monotonic()
                if not existing_aim_ready:
                    if time.monotonic()-existing_aim_since>5: raise RuntimeError('Existing-block camera aim exceeded 5s bound')
                    movement_aim_x=math.copysign(max(.2,min(.8,abs(delta)/45)),delta)
            if args.scripted_movement_probe:
                probe_ready_since = (probe_ready_since or time.monotonic()) if authority.active and existing_aim_ready else None
                if probe is None and probe_ready_since is not None and time.monotonic()-probe_ready_since>2.5:
                    fixture_record=read_seqlock(link.memory,0xc80,24)
                    if fixture_record is not None:
                        fixture_seq,fixture_host,bx,by,bz,fixture_valid=struct.unpack('<IIiiiI',fixture_record)
                        if fixture_seq and fixture_host==os.getpid() and fixture_valid==1:
                            probe=ScriptedMovement((bx,by,bz),args.scripted_support_seconds,args.scripted_jump_on_target)
                if probe is not None:
                    wanted=probe.step(time.monotonic(),mc,position,authority.active and movement_error is None,camera_eye=eye)
                    if probe.finished and not probe.passed and not probe.reported:
                        probe.reason += ': '+str(movement_error or authority.reason)
                    for code in sorted(probe_keys-wanted):link.key(code,False)
                    for code in sorted(wanted-probe_keys):link.key(code,True)
                    probe_keys=wanted
                    if probe.finished:
                        struct.pack_into('<I',link.memory,0xc6c,0)
                        if not probe.reported:
                            (ROOT/'scripted-movement-validation.json').write_text(json.dumps(probe.report(),indent=2))
                            probe.reported=True
                elif time.monotonic()-probe_wait_since>args.probe_ready_timeout:
                    raise RuntimeError('Scripted probe did not gain ready foreground authority')
            if args.scripted_controls_probe:
                controls_ready_since = (controls_ready_since or time.monotonic()) if authority.active else None
                if controls is None and controls_ready_since is not None and time.monotonic()-controls_ready_since>2.5:
                    controls = ScriptedControls()
                if controls is not None and not controls.reported:
                    wanted=controls.step(time.monotonic(),mc,position,authority.active and movement_error is None)
                    for code in sorted(controls_keys-wanted):link.key(code,False)
                    for code in sorted(wanted-controls_keys):link.key(code,True)
                    controls_keys=wanted
                    if controls.finished:
                        link.event(6,0)
                        struct.pack_into('<I',link.memory,0xc6c,0)
                        (ROOT/'scripted-controls-validation.json').write_text(json.dumps(controls.report(),indent=2))
                        controls.reported=True
                elif controls is None and time.monotonic()-probe_wait_since>args.probe_ready_timeout:
                    raise RuntimeError('Controls probe did not gain ready foreground authority')
            if placement is not None:
                placement_stick,events=placement.step(time.monotonic(),mc,authority.active and movement_error is None)
                for event in events:link.event(*event)
                if placement.finished:
                    struct.pack_into('<I',link.memory,0xc6c,0)
                    if not placement_reported:
                        (ROOT/'scripted-placement-validation.json').write_text(json.dumps(placement.report(),indent=2))
                        placement_reported=True
            if pending_move_since is not None:
                command=process.get(0x10)
                outcome=completion(command,process.get(0x14,'i'),time.monotonic()-pending_move_since,authority.active)
                if outcome=='complete':
                    pending_move_since=None
                elif outcome in ('rejected','stalled'):
                    if command==3:process.set(0x10,0)
                    if outcome=='rejected':
                        movement_error='Player hook rejected correction'
                    else:
                        # Loading/focus pauses can skip a player tick. Keep the
                        # acquired epoch; retry only a fresh, bounded target.
                        movement_stalls+=1
                        movement_retry_until=time.monotonic()+.25
                    pending_move_since=None
                elif outcome=='released':
                    if command==3:process.set(0x10,0)
                    pending_move_since=None
            if authority.active and movement_error is None:
                # Do not echo Minecraft-driven movement back as repeated teleports.
                initial = position
                if point is not None and pending_move_since is None and time.monotonic()>=movement_retry_until:
                    try:
                        if process.nudge(point,rebase=True): pending_move_since = time.monotonic()
                    except (ValueError,OSError) as exc:
                        movement_error = str(exc)
            elif not authority.retains_session(now_ms=link.kernel.GetTickCount64(),
                    mc_heartbeat=struct.unpack_from('<Q',link.memory,0x18)[0],mc=mc,teleport=teleport) and sum((a-b)**2 for a, b in zip(position, initial)) > 0.04:
                teleport += 1
                initial = position
            viewport = struct.unpack_from('<II', link.memory, 0xc40)
            if not (640 <= viewport[0] <= 3840 and 360 <= viewport[1] <= 2160):
                viewport = (1280,720)
            # Front presentation looks opposite the gameplay aim. Keep Minecraft
            # movement/picking yaw on the native orbit while meshes use real view.
            native_camera_mode=0
            gameplay_direction=last_gameplay_direction or direction
            if args.first_person:
                try:
                    native_camera_mode,gameplay_direction=process.orbit_view()
                    last_gameplay_direction=gameplay_direction
                except ValueError: pass
            link.publish(initial, direction, teleport, *viewport, eye=eye, fov=projection['fov'], projection=projection, gameplay_direction=gameplay_direction)
            if not args.renderer:
                link.drain_render()
            mc = link.mc()
            if args.renderer:
                # Own mailbox flag makes the PPC input hook clear all GamePad touch samples.
                # It prevents Minecraft right-clicks from becoming Cemu screen taps.
                input_enabled=struct.unpack_from('<I',link.memory,0xc48)[0]
                # HyruleCraft owns the TV presentation throughout a live MC world,
                # even while F7 has released keyboard/mouse movement. A click
                # must never become an unrelated Wii U GamePad touchscreen tap.
                mc_age=link.kernel.GetTickCount64()-struct.unpack_from('<Q',link.memory,0x18)[0]
                suppress_touch=bool(mc and mc['flags']&1 and 0<=mc_age<=500)
                process.set(0x1a0,int(suppress_touch))
                cells=[ctypes.c_long.from_buffer(link.memory,off) for off in (0xc54,0xc58)]
                dx,dy=(link.exchange(ctypes.byref(cell),0) for cell in cells)
                del cells
                if args.first_person and mc:
                    cam_mode = mc.get('camera_mode', 0)
                    mc_age=link.kernel.GetTickCount64()-struct.unpack_from('<Q',link.memory,0x18)[0]
                    front_mode=cam_mode if cam_mode in (1,2) and mc['flags']&1 and not mc['flags']&32 and 0<=mc_age<=500 else 0
                    camera_distance=mc.get('camera_distance',0.)
                    if not math.isfinite(camera_distance): camera_distance=0.
                    process.set(0x1f0,max(.1,min(6.,camera_distance)),'f')
                    process.set(0x1c8,process.get(0x1cc))
                    process.set(0x1c4,front_mode)
                    renderer_age=link.kernel.GetTickCount64()-struct.unpack_from('<Q',link.memory,0xc60)[0]
                    avatar_ready=struct.unpack_from('<I',link.memory,0xc74)[0]==1
                    process.set(0x1f4,int(front_mode!=0 and avatar_ready and 0<=renderer_age<=500))
                    desired_fp = 1 if cam_mode == 0 else 0
                    if desired_fp != current_fp_mode:
                        process.set(0x1b4, desired_fp)
                        current_fp_mode = desired_fp

                if input_enabled and mc and not mc['flags']&2:
                    direct_mouse.step(dx,dy,mc.get('sensitivity',.5),gameplay_direction)
                    step_x, step_y = (0.,0.)
                    deadzone = 0.16
                    comp_x = math.copysign(deadzone + abs(step_x) * (1.0 - deadzone), step_x) if step_x != 0.0 else 0.0
                    comp_y = math.copysign(deadzone + abs(step_y) * (1.0 - deadzone), step_y) if step_y != 0.0 else 0.0
                    process.put(0x48,struct.pack('>ffff',0,0,comp_x,comp_y))
                    process.set(0x3c,0)
                    # Keep the VPAD override leased for neutral frames too.
                    # Disabling it at release never guarantees BOTW consumes
                    # the zero we just wrote; it can retain its previous sample.
                    process.set(0x198,1)
                else:
                    mouse_look.reset()
                    if not ((any(placement_stick) or movement_aim_x) and authority.active): process.set(0x198,0)
            if any(placement_stick) and authority.active:
                process.put(0x48,struct.pack('>ffff',0,0,*placement_stick))
                process.set(0x3c,0);process.set(0x198,1)
            if movement_aim_x and authority.active:
                process.put(0x48,struct.pack('>ffff',0,0,movement_aim_x,0))
                process.set(0x3c,0);process.set(0x198,1)
            if mouse_probe and not mouse_probe.reported:
                ready=bool(mc and mc['flags']&256 and mc['teleport_ack']==teleport)
                probe_stick=mouse_probe.step(time.monotonic(),direction,ready)
                if probe_stick is not None:
                    direct_mouse.step(*probe_stick,.5,gameplay_direction)
                    process.put(0x48,struct.pack('>ffff',0.,0.,0.,0.))
                    process.set(0x3c,0);process.set(0x198,1)
                if mouse_probe.finished:
                    (ROOT/'mouse-stop-validation.json').write_text(json.dumps(mouse_probe.report(expected_turn=12*args.mouse_scale),indent=2))
                    mouse_probe.reported=True
            # Shared native camera/support lease. Publish an even generation only
            # after all fields are written; no native physics offsets are written.
            world_fresh=bool(mc and mc['flags']&1 and not mc['flags']&32 and
                0<=link.kernel.GetTickCount64()-struct.unpack_from('<Q',link.memory,0x18)[0]<=500)
            own_camera=world_fresh and (not args.no_input or (mouse_probe is not None and direct_mouse.yaw is not None))
            native_flags=int(own_camera) | (2 if authority.active and movement_error is None else 0)
            native_direction=direct_mouse.step(0,0,.5,gameplay_direction) if own_camera else gameplay_direction
            direct_seq+=2
            process.set(0x44,direct_seq-1)
            process.put(0x5c,struct.pack('>fff',*native_direction))
            process.set(0x68,process.get(0x1cc))
            process.set(0x40,native_flags)
            process.set(0x44,direct_seq)
            frame = None if args.renderer else link.overlay()
            if mc and mc['flags'] & 1:
                world_ready_since = world_ready_since or time.monotonic()
            settled = world_ready_since is not None and time.monotonic() - world_ready_since > 4
            if frame and settled and mc and not mc['flags'] & 2 and not hud_saved:
                save_png(ROOT / 'minecraft-hud.png', frame)
                hud_saved = True
            if args.inventory_probe and settled and mc and mc['flags'] & 1 and not inventory_opened:
                link.key(8, True)  # SDL E: actual Minecraft inventory handler.
                link.key(8, False)
                inventory_opened = True
            if frame and inventory_opened and mc and mc['flags'] & 2:
                save_png(ROOT / 'minecraft-inventory.png', frame)
                args.inventory_probe = False
                inventory_opened = False
            now = time.monotonic()
            if now - last_report > 2:
                last_report = now
                mouse_diag = None
                if args.renderer:
                    diag_raw = struct.unpack_from('<IIiiiiIIII', link.memory, 0xca0)
                    mouse_diag = dict(
                        read_failures=diag_raw[0],
                        warp_failures=diag_raw[1],
                        last_raw_cursor=(diag_raw[2], diag_raw[3]),
                        last_center_screen=(diag_raw[4], diag_raw[5]),
                        captured=bool(diag_raw[6]),
                        samples=diag_raw[7],
                        accumulated_deltas=(diag_raw[8], diag_raw[9])
                    )
                report = dict(botw_pid=args.pid, botw_position=position, camera_projection=projection, minecraft=mc,
                              native_camera_mode=native_camera_mode, native_camera_eye=eye, native_camera_direction=direction, viewport=viewport,
                              render_messages=link.render_counts, overlay_frames=link.overlay_frames,
                              renderer_implemented=args.renderer,
                              depth_available=bool(struct.unpack_from('<I',link.memory,0xc4c)[0]),
                              mouse_diagnostics=mouse_diag,
                              controls_state=dict(input_enabled=bool(struct.unpack_from('<I',link.memory,0xc48)[0]),
                                  physical_source='external-host' if capture else 'disabled',
                                  held_key_count=sum(link.memory[0xd00:0xe00])),
                              terrain_collision_implemented=terrain_report is not None,
                              terrain_coverage=terrain_report,
                              terrain_collision_complete=False,
                              terrain_collision_ready=bool(mc and mc['flags'] & (1<<8)),
                              movement_authority='Minecraft' if authority.active and movement_error is None else 'BOTW',
                              movement_reason=movement_error or authority.reason,
                              scripted_probe=None if probe is None else dict(stage=probe.stage,finished=probe.finished,reason=probe.reason),
                              scripted_controls=None if controls is None else dict(kind=type(controls).__name__,stage=controls.stage,finished=controls.finished,reason=controls.reason),
                              input_capture_allowed=not args.no_input,
                              movement_mode_requested=args.mc_movement,
                              movement_stalls=movement_stalls,
                              movement_retry_pending=time.monotonic()<movement_retry_until,
                              phase='live-minecraft-renderer' if args.renderer else 'real-engine-link-probe')
                (ROOT / 'link-status.json').write_text(json.dumps(report, indent=2))
                if now-start<5 or int(now-start)%10<2:
                    print(json.dumps(report), flush=True)
            time.sleep(1/60)
    except OSError:
        # Normal window close invalidates native memory while the host samples.
        # Treat only a signaled verified process handle as a clean shutdown.
        if process.k.WaitForSingleObject(process.handle,0)!=0:raise
        print('HyruleCraft: Cemu closed; releasing input and saving Minecraft.',flush=True)
    finally:
        try:
            (ROOT/'link-status.json').write_text(json.dumps(dict(phase='stopped',botw_pid=args.pid,
                input_capture_allowed=False,movement_authority='BOTW',movement_reason='bridge stopped'),indent=2))
        except OSError:pass
        if terrain_loader:
            terrain_loader.close()
        try:link.event(6,0)
        except RuntimeError:pass
        for code in probe_keys | controls_keys:
            try:link.key(code,False)
            except RuntimeError:pass
        struct.pack_into('<I', link.memory, 0xc6c, 0)
        struct.pack_into('<I', link.memory, 0xc68, 0)
        struct.pack_into('<I', link.memory, 0xc48, 0)
        struct.pack_into('<Q', link.memory, 0x10, 0)
        if capture:
            capture.close()
        try:
            if pending_move_since is not None and process.get(0x10)==3:
                process.set(0x10,0)
            process.set(0x40,0)
            process.set(0x1a0,0)
            process.set(0x198,0)
            if args.first_person:
                process.set(0x1b4,0)
                process.set(0x1c4,0)
                process.set(0x1f4,0)
        except (ValueError,OSError):
            pass
        process.k.CloseHandle(process.handle)
        link.close()


if __name__ == '__main__':
    main()

