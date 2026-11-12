"""Experimental BOTW companion: signature-gated mailbox, Creative HUD and input.

Only attaches to an explicit lab Cemu PID and writes the mod's own mailbox.
Game functions run from the Cemu graphic pack on BOTW's execution thread.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import math
from pathlib import Path
import re
import struct
import time

from geometry import normalize, ray_box, snap
from generated.design import BLOCKS, FIELDS

ROOT = Path(__file__).resolve().parent
MAGIC = b'HYRULEBLOCKS_v03'
LOG = ROOT / 'runtime.log'


def log(message):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+str(message)+'\n')


class Process:
    def __init__(self, pid, log_path):
        self.pid = pid
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        self.k.WriteProcessMemory.argtypes = self.k.ReadProcessMemory.argtypes
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        self.k.WaitForSingleObject.restype = W.DWORD
        self.handle = self.k.OpenProcess(0x10 | 0x20 | 0x8 | 0x1000 | 0x100000, False, pid)
        if not self.handle:
            raise OSError(C.get_last_error(), 'Cannot access test Cemu')
        try:
            image = C.create_unicode_buffer(32768)
            size = W.DWORD(32768)
            if not self.k.QueryFullProcessImageNameW(self.handle, 0, image, C.byref(size)):
                raise OSError('Cannot validate target executable')
            if Path(image.value).resolve() != (Path(log_path).parent / 'Cemu.exe').resolve():
                raise ValueError('PID does not belong to the requested lab Cemu')
            content = Path(log_path).read_text(errors='replace')
            if 'TitleVersion: v208' not in content or 'TitleId: 00050000-101c9400' not in content:
                raise ValueError('Only US BOTW update 208 has been checked')
            matches = re.findall(r'Init Wii U memory space \(base: (0x[0-9a-fA-F]+)\)', content)
            if not matches:
                raise ValueError('Cemu memory base missing from log')
            self.base = int(matches[-1], 16)
            self.box = None
            for offset in range(0x01800000, 0x01C00000, 65536):
                try:
                    data = self.read(self.base + offset, 65536)
                except OSError:
                    continue
                index = data.find(MAGIC)
                if index >= 0:
                    self.box = self.base + offset + index
                    break
            if self.box is None:
                raise ValueError('Hyrule Blocks patch signature missing; no memory will be written')
            log(f'Connected to lab Cemu PID={pid}, mailbox={self.box:#x}')
        except BaseException:
            self.k.CloseHandle(self.handle)
            self.handle = None
            raise

    def is_running(self):
        result = self.k.WaitForSingleObject(self.handle, 0)
        if result == 0xffffffff:
            raise OSError(C.get_last_error(), 'Cannot check test Cemu lifetime')
        return result == 0x102

    def read(self, address, size):
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, address, buffer, size, C.byref(count)) or count.value != size:
            raise OSError(C.get_last_error(), f'Read failed at {address:#x}')
        return buffer.raw

    def get(self, offset, kind='I'):
        return struct.unpack('>'+kind, self.read(self.box+offset, struct.calcsize(kind)))[0]

    def put(self, offset, data):
        data = bytes(data)
        if self.read(self.box, 16) != MAGIC:
            raise ValueError('Bridge signature disappeared')
        if offset < 16 or offset+len(data) > 640:
            raise ValueError('Write outside mod mailbox')
        count = C.c_size_t()
        if not self.k.WriteProcessMemory(self.handle, self.box+offset, data, len(data), C.byref(count)):
            raise OSError(C.get_last_error(), 'Mailbox write failed')
        if count.value != len(data):
            raise OSError('Partial mailbox write')

    def set(self, offset, value, kind='I'):
        self.put(offset, struct.pack('>'+kind, value))

    def position(self, actor=None):
        actor = actor or self.get(0x20)
        if not 0x10000000 <= actor <= 0xE0000000:
            raise ValueError('No live player actor')
        values = tuple(struct.unpack('>f', self.read(self.base+actor+FIELDS[f'position-{axis}'].offset, 4))[0] for axis in 'xyz')
        if not all(math.isfinite(v) and abs(v) < 20000 for v in values):
            raise ValueError('Player position is invalid')
        return values

    def view(self):
        # Camera::getLookAtCamera: singleton+0x14 -> buffer+0xc0.
        # Verified v208 PPC getter selects pointer index at +4, entries at +8.
        owner = struct.unpack('>I', self.read(self.base+int(FIELDS['camera-singleton'].offset,0),4))[0]
        if not 0x10000000 <= owner <= 0xE0000000:
            raise ValueError('No gameplay camera')
        buffer = owner + FIELDS['camera-buffer'].offset
        index = struct.unpack('>i', self.read(self.base+buffer+4,4))[0]
        if index < 0:
            raise ValueError('Gameplay camera is not ready')
        camera = struct.unpack('>I',self.read(self.base+buffer+8+(index*4 if index<2 else 0),4))[0]
        if not 0x10000000 <= camera <= 0xE0000000:
            raise ValueError('Invalid gameplay camera')
        values = struct.unpack('>6f',self.read(self.base+camera+0x34,24))
        eye, at = values[:3], values[3:]
        if not all(math.isfinite(x) and abs(x)<20000 for x in values):
            raise ValueError('Invalid camera transform')
        if sum((a-b)**2 for a,b in zip(eye,self.position())) > 2500:
            raise ValueError('Camera is too far away for Creative building')
        return eye, normalize(tuple(a-b for a,b in zip(at,eye)))

    def orbit_view(self):
        """Generation-paired native gameplay direction and detached-camera mode."""
        for _ in range(8):
            first=self.get(0x1ec)
            if first&1: continue
            raw=self.read(self.box+0x1d0,16)
            if first!=self.get(0x1ec): continue
            mode,x,y,z=struct.unpack('>Ifff',raw)
            values=(x,y,z)
            if first and mode in (0,1,2) and all(math.isfinite(v) for v in values) and sum(v*v for v in values)>1e-6:
                return mode,normalize(values)
        raise ValueError('Native camera orientation not published')

    def direction(self):
        return self.view()[1]

    def nudge(self, point, max_distance=0.75, *, rebase=False):
        """Bounded correction through the player-tick command, not direct transforms."""
        current = self.position()
        if not all(math.isfinite(v) and abs(v) < 20000 for v in point):
            raise ValueError('Invalid movement position')
        distance = math.dist(point, current)
        if rebase:
            # The player can move between the host sample and this mailbox read.
            # Recompute a bounded step from this newer position, never turn an
            # ordinary gravity/sample race into permanent movement shutdown.
            if not math.isfinite(max_distance) or max_distance <= 0:
                raise ValueError('Invalid movement distance limit')
            factor = min(1., min(.5, max_distance) / distance) if distance else 1.
            point = tuple(a+(b-a)*factor for a,b in zip(current,point))
        elif distance > max_distance:
            raise ValueError('Movement exceeds the per-command distance limit')
        if self.get(0x10) or self.get(0x190):
            return False
        # The hook independently checks these exact US v208 Link addresses.
        actor = self.get(0x20)
        table = struct.unpack('>I',self.read(self.base+actor+0xe8,4))[0]
        if table != 0x101e5ffc or struct.unpack('>I',self.read(self.base+table+0x2ac,4))[0] != 0x02d66abc:
            raise ValueError('Unverified player setMtx; movement refused')
        self.put(0x1b8,struct.pack('>fff',*point))
        self.set(0x14,0)
        self.set(0x10,3)
        return True

    def recover_home(self, point):
        """One explicit nearby return through the verified game's WarpTo API."""
        if len(point)!=3 or not all(math.isfinite(v) and abs(v)<20000 for v in point):
            raise ValueError('Invalid recovery point')
        if math.dist(point,self.position())>96:raise ValueError('Recovery point exceeds 96m local bound')
        if self.get(0x10) or self.get(0x190):return False
        actor=self.get(0x20)
        table=struct.unpack('>I',self.read(self.base+actor+0xe8,4))[0]
        if table!=0x101e5ffc or struct.unpack('>I',self.read(self.base+table+0x2ac,4))[0]!=0x02d66abc:
            raise ValueError('Unverified player setMtx; recovery refused')
        self.set(0x40,0)
        self.put(0x1b8,struct.pack('>fff',*point));self.set(0x14,0);self.set(0x10,4)
        return True

    def ready(self):
        return bool(self.get(0x1C) and self.get(0x20) and not self.get(0x10) and not self.get(0x190))

    def place(self, point, actor=None):
        actor = actor or BLOCKS['wood'].actor
        if not self.ready():
            raise ValueError('Game is not ready for placement')
        if not all(math.isfinite(v) and abs(v) < 20000 for v in point):
            raise ValueError('Invalid placement position')
        args = bytearray(self.read(self.box+0x70, 104))
        # Source SpawnActors reverses the entire actor-storage struct. These are
        # its resulting big-endian byte offsets, not the pre-reversal indices.
        for off in (40, 32, 36, 24, 8, 52):
            struct.pack_into('>I', args, off, 0)
        for off in (44, 48, 28):
            struct.pack_into('>I', args, off, 0xFFFFFFFF)
        struct.pack_into('>fff', args, 56, *point)
        struct.pack_into('>f', args, 68, 0.0)
        struct.pack_into('>H', args, 72, 0)
        struct.pack_into('>I', args, 0, 0x16)
        struct.pack_into('>I', args, 4, 0x043B0000)
        self.put(0xE0, args)
        name = actor.encode('ascii')
        if len(name) > 63:
            raise ValueError('Actor name too long')
        self.put(0x150, name.ljust(64, b'\0'))
        self.set(0x14, 0)
        self.set(0x10, 1)  # publish request last
        log(f'Placement requested: {actor} at {point}')

    def remove(self, actor):
        if not self.ready() or not 0x10000000 <= actor <= 0xE0000000:
            raise ValueError('Removal refused: invalid state')
        name_ptr = struct.unpack('>I', self.read(self.base+actor+4, 4))[0]
        name = self.read(self.base+name_ptr, 64).split(b'\0')[0]
        if name != BLOCKS['wood'].actor.encode('ascii'):
            raise ValueError('Removal refused: actor identity changed')
        state = self.read(self.base+actor+0x54, 1)[0]
        if state > 2:
            raise ValueError('Actor is already deleted')
        self.set(0x34, actor)
        self.set(0x14, 0)
        self.set(0x10, 2)
        log(f'Removal requested: actor={actor:#x}')

    def close(self, reset_mailbox=True):
        # Passive readers (launcher readiness checks) own no input/camera flags.
        # Closing their handle must not cancel another actor's current request.
        if reset_mailbox:
            try:
                self.set(0x198, 0)
                self.set(0x1A0, 0)
                self.set(0x1B4, 0)
                self.set(0x1C4, 0)
                self.set(0x1F4, 0)
            except (OSError, ValueError):
                pass
        self.k.CloseHandle(self.handle)


class HUD:
    def __init__(self, process):
        process.k.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR]
        process.k.CreateMutexW.restype=W.HANDLE
        self.instance=process.k.CreateMutexW(None,False,f'Local\\HyruleBlocksHUD-{process.pid}')
        if not self.instance:
            raise OSError(C.get_last_error(),'Could not create companion instance lock')
        if C.get_last_error()==183:
            process.k.CloseHandle(self.instance)
            log('Companion already running; duplicate launch ignored')
            return
        import tkinter as tk
        self.tk, self.p = tk, process
        self.user = C.WinDLL('user32', use_last_error=True)
        self.user.GetForegroundWindow.restype = W.HWND
        self.user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        self.user.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        self.user.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
        self.user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
        self.user.GetParent.argtypes = [W.HWND]
        self.user.GetParent.restype = W.HWND
        self.user.GetAsyncKeyState.argtypes = [C.c_int]
        self.user.GetWindowLongPtrW.argtypes = [W.HWND, C.c_int]
        self.user.GetWindowLongPtrW.restype = C.c_ssize_t
        self.user.SetWindowLongPtrW.argtypes = [W.HWND, C.c_int, C.c_ssize_t]
        self.root = tk.Tk()
        self.root.title('Hyrule Blocks HUD')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', '#ff00ff')
        self.canvas = tk.Canvas(self.root, bg='#ff00ff', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.block_icon = tk.PhotoImage(file=str(ROOT/'assets/pixel-planks.png')).zoom(2,2) if (ROOT/'assets/pixel-planks.png').exists() else None
        self.root.update()
        hwnd = self.user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        self.user.SetWindowLongPtrW(hwnd, -20, self.user.GetWindowLongPtrW(hwnd, -20) | 0x20 | 0x08000000)
        self.building, self.inventory, self.selected = False, False, 0
        self.first_person = False
        self.menu_held,self.menu_until = 0,0
        self.mouse_edges = set()
        self.install_mouse_capture()
        self.keys, self.pad, self.pending = {}, 0, None
        self.key_events = {}
        self.sample_keys()  # discard presses that predate this companion
        self.blocks = []
        self.status = 'F6 / D-pad up: Creative build mode'
        self.last_frame = self.p.get(0x18)
        self.last_tick = time.monotonic()
        self.pending_since = None
        self.root.after(16, self.tick)
        self.root.mainloop()
        self.user.UnhookWindowsHookEx(self.mouse_hook)
        process.k.CloseHandle(self.instance)

    def install_mouse_capture(self):
        # Capture only button messages destined for this game while Creative is on.
        # Low-level suppression stops Cemu's own touch/gyro processing too.
        callback_type = C.WINFUNCTYPE(C.c_ssize_t,C.c_int,W.WPARAM,W.LPARAM)
        self.user.SetWindowsHookExW.argtypes = [C.c_int,callback_type,W.HINSTANCE,W.DWORD]
        self.user.SetWindowsHookExW.restype = W.HANDLE
        self.user.CallNextHookEx.argtypes = [W.HANDLE,C.c_int,W.WPARAM,W.LPARAM]
        self.user.CallNextHookEx.restype = C.c_ssize_t
        self.user.UnhookWindowsHookEx.argtypes = [W.HANDLE]
        def receive(code,message,data):
            if code >= 0 and message in (0x201,0x202,0x204,0x205) and self.building:
                pid = W.DWORD()
                self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),C.byref(pid))
                if pid.value == self.p.pid:
                    if message in (0x201,0x204) and not self.inventory:
                        self.mouse_edges.add(1 if message==0x201 else 2)
                    return 1
            return self.user.CallNextHookEx(None,code,message,data)
        self.mouse_callback = callback_type(receive)
        self.mouse_hook = self.user.SetWindowsHookExW(14,self.mouse_callback,None,0)
        if not self.mouse_hook:
            raise OSError(C.get_last_error(),'Mouse click capture could not be installed')

    def sample_keys(self):
        for key in range(1,256):
            state = self.user.GetAsyncKeyState(key)
            down = bool(state & 0x8000)
            edge = bool(state & 1) or (down and not self.keys.get(key,False))
            self.keys[key] = down
            self.key_events[key] = down, edge
        for key in self.mouse_edges:
            self.key_events[key] = False, True
        self.mouse_edges.clear()

    def key(self, key):
        return self.key_events.get(key,(False,False))

    def draw(self, width, height):
        c = self.canvas
        c.delete('all')
        if not self.building:
            c.create_text(width/2, height-32, text=self.status, fill='white', font=('Consolas', 12))
            return
        x, y = width/2, height/2
        for coordinates in ((x-8,y,x+8,y),(x,y-8,x,y+8)):
            c.create_line(*coordinates, fill='#151515', width=4)
            c.create_line(*coordinates, fill='white', width=2)
        start, top = width/2-9*24, height-72
        for slot in range(9):
            left = start+48*slot
            c.create_rectangle(left, top, left+46, top+46, fill='#404040', outline='white' if slot==self.selected else '#777777', width=3 if slot==self.selected else 1)
            if slot == 0:
                if self.block_icon:
                    c.create_image(left+23,top+24,image=self.block_icon)
                else:
                    c.create_rectangle(left+11, top+10, left+35, top+34, fill='#956039', outline='#d6a56b', width=2)
                c.create_text(left+36, top+37, text='∞', fill='white')
            c.create_text(left+6,top+7,text=str(slot+1),fill='#cccccc',font=('Consolas',8))
        c.create_text(width/2, top-16, text=self.status, fill='white', font=('Consolas',11))
        if self.inventory:
            c.create_rectangle(width/2-180,height/2-130,width/2+180,height/2+130,fill='#c6c6c6',outline='#333333',width=4)
            c.create_text(width/2,height/2-95,text='CREATIVE INVENTORY',fill='#222222',font=('Consolas',18,'bold'))
            c.create_rectangle(width/2-22,height/2-24,width/2+22,height/2+20,fill='#956039',outline='#4a3321',width=3)
            c.create_text(width/2,height/2+55,text='Wood · unlimited\nE / minus to close',fill='#222222',font=('Consolas',13))

    def tick(self):
        try:
            self.sample_keys()  # consume edges even when building is disabled
            frame = self.p.get(0x18)
            if frame != self.last_frame:
                self.last_frame, self.last_tick = frame, time.monotonic()
            if time.monotonic()-self.last_tick > 30:
                raise ValueError('Game bridge stopped ticking')
            if self.pending and self.p.get(0x14) == 2 and self.p.get(0x24):
                self.blocks.append((self.p.get(0x24), self.pending))
                self.pending = None
                self.status = f'Placed · {len(self.blocks)}/32 blocks'
                log(self.status)
            if self.pending and self.p.get(0x14, 'i') == -1:
                self.pending = None
                self.status = 'BOTW rejected placement; see runtime.log'
            if self.pending and self.pending_since and time.monotonic()-self.pending_since > 10:
                self.status = 'Actor creation did not complete; placement remains unverified'
            hwnd = self.user.GetForegroundWindow()
            pid = W.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value != self.p.pid:
                self.root.withdraw()
                self.p.set(0x198, 0)
                self.p.set(0x1A0, 0)
                self.root.after(16, self.tick)
                return
            rect, origin = W.RECT(), W.POINT()
            self.user.GetClientRect(hwnd, C.byref(rect))
            self.user.ClientToScreen(hwnd, C.byref(origin))
            width, height = rect.right, rect.bottom
            self.root.geometry(f'{width}x{height}+{origin.x}+{origin.y}')
            self.root.deiconify()
            pad = self.p.get(0x58)
            pad_edge, self.pad = pad & ~self.pad, pad
            if self.key(0x74)[1] or pad_edge & 0x0100:
                self.first_person = not self.first_person
                self.status = 'First person' if self.first_person else 'Third person'
            self.p.set(0x1B4,int(self.first_person))
            if self.key(0x75)[1] or pad_edge & 0x0200:
                self.building = not self.building
                self.status = 'Creative · RMB/ZR place · LMB/ZL break'
            if self.key(0x45)[1] or pad_edge & 4:
                self.inventory = not self.inventory
            if self.key(0x1B)[1]:
                self.building = False
            for slot in range(9):
                if self.key(0x31+slot)[1]:
                    self.selected = slot
            if pad_edge & 0x0800:
                self.selected = (self.selected-1)%9
            if pad_edge & 0x0400:
                self.selected = (self.selected+1)%9
            self.p.set(0x1A0, int(self.building))
            self.p.set(0x1A4, int(self.inventory and self.building))
            if self.building and not self.inventory:
                if self.key(2)[1] or pad_edge & 0x0040:
                    if self.selected != 0:
                        self.status = 'Select slot 1: wood'
                    elif len(self.blocks) < BLOCKS['wood'].limit and not self.pending:
                        pos = self.p.position()
                        eye, direction = self.p.view()
                        distance = math.sqrt(sum((a-b)**2 for a,b in zip(eye,pos))) + 4
                        target = snap(tuple(eye[i]+direction[i]*distance for i in range(3)),BLOCKS['wood'].grid)
                        if target in [b[1] for b in self.blocks]:
                            self.status = 'That grid cell is occupied'
                        else:
                            self.p.place(target)
                            self.pending = target
                            self.pending_since = time.monotonic()
                            self.status = 'Waiting for BOTW actor creation…'
                if self.key(1)[1] or pad_edge & 0x0080:
                    pos = self.p.position()
                    eye, direction = self.p.view()
                    reach = math.sqrt(sum((a-b)**2 for a,b in zip(eye,pos))) + 8
                    candidates = []
                    for block in self.blocks:
                        block_origin = self.p.position(block[0])
                        center = (block_origin[0],block_origin[1]+BLOCKS['wood'].pivot_to_center_y,block_origin[2])
                        hit = ray_box(eye,direction,center,BLOCKS['wood'].half_extent,reach)
                        if hit is not None and hit <= reach:
                            candidates.append((hit,block))
                    if candidates:
                        _, block = min(candidates,key=lambda x:x[0])
                        self.p.remove(block[0])
                        self.blocks.remove(block)
                        self.status = 'Removal requested'
                self.keyboard(hwnd,origin,width,height)
            else:
                held = 0
                if not self.building:
                    for key,button in ((0x0D,0x8000),(0x08,0x4000),(0x26,0x0200),(0x28,0x0100),(0x25,0x0800),(0x27,0x0400)):
                        down,edge=self.key(key)
                        if down or edge: held |= button
                    if held:
                        self.menu_held,self.menu_until=held,time.monotonic()+0.1
                    elif time.monotonic()<self.menu_until:
                        held=self.menu_held
                self.p.put(0x48,struct.pack('>ffff',0,0,0,0))
                self.p.set(0x3C,held)
                self.p.set(0x198,int(bool(held)))
            self.draw(width,height)
        except (OSError,ValueError) as e:
            self.status = str(e)
            log(e)
            try:
                self.p.set(0x198,0)
            except (OSError,ValueError):
                self.root.destroy()
                return
        self.root.after(16,self.tick)

    def keyboard(self, hwnd, origin, width, height):
        left = float(self.key(0x44)[0])-float(self.key(0x41)[0])
        forward = float(self.key(0x57)[0])-float(self.key(0x53)[0])
        held = (0x2000 if self.key(0x20)[0] else 0) | (0x4000 if self.key(0x10)[0] else 0) | (0x8000 if self.key(0x46)[0] else 0)
        cursor = W.POINT()
        self.user.GetCursorPos(C.byref(cursor))
        center = (origin.x+width//2, origin.y+height//2)
        mx,my = cursor.x-center[0],cursor.y-center[1]
        keyboard_active = bool(left or forward or held or mx or my)
        if keyboard_active:
            self.user.SetCursorPos(*center)
        self.p.put(0x48,struct.pack('>ffff',left,forward,max(-1,min(1,mx/50)),max(-1,min(1,-my/50))))
        self.p.set(0x3C,held)
        self.p.set(0x198,int(keyboard_active))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--probe',action='store_true')
    parser.add_argument('--place',nargs=3,type=float)
    parser.add_argument('--remove',type=lambda x:int(x,0))
    parser.add_argument('--button',type=lambda x:int(x,0))
    parser.add_argument('--details',action='store_true')
    parser.add_argument('--reset-failed',action='store_true')
    args = parser.parse_args()
    process = Process(args.pid,args.log)
    try:
        if args.reset_failed:
            if process.get(0x24) or process.get(0x1A8) != 0:
                raise ValueError('Only a rejected request with no created actor may be reset')
            process.set(0x190,0)
            process.set(0x10,0)
            process.set(0x14,0)
            print('Rejected request cleared; no game object removed.')
        elif args.details:
            print(json.dumps({'creator':hex(process.get(0x28)),'heap':hex(process.get(0x2C)), 'template_words': [hex(v) for v in struct.unpack('>26I',process.read(process.box+0x70,104))], 'request_words':[hex(v) for v in struct.unpack('>26I',process.read(process.box+0xE0,104))]}))
        elif args.button is not None:
            process.put(0x48,struct.pack('>ffff',0,0,0,0))
            process.set(0x3C,args.button)
            process.set(0x198,1)
            time.sleep(0.15)
            process.set(0x3C,0)
            time.sleep(0.1)
            print('Gamepad button sent through mod input bridge.')
        elif args.probe:
            result = {'pid':args.pid,'frame':process.get(0x18),'template':process.get(0x1C),'player':hex(process.get(0x20)),'pending':process.get(0x190),'result':process.get(0x14),'actor':hex(process.get(0x24)), 'create_return':hex(process.get(0x1A8))}
            if result['player'] != '0x0':
                result['position'] = process.position()
                result['forward'] = process.direction()
            print(json.dumps(result))
        elif args.place:
            process.place(args.place)
            print('Requested placement; in-game confirmation still required.')
        elif args.remove:
            process.remove(args.remove)
            print('Requested removal; in-game confirmation still required.')
        else:
            HUD(process)
    finally:
        process.close()


if __name__ == '__main__':
    main()
