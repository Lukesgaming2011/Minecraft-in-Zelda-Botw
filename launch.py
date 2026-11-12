"""HyruleCraft hardened unified launcher.

Coordinates starting the verified Minecraft dev-instance, isolated Cemu 2.6
with US BOTW v208, memory bridge readiness, and host_link.py execution.
"""
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as W
import json
import hashlib
import shutil
import os
from pathlib import Path
import subprocess
import sys
import time

from runtime_config import load_config, inspect_setup, native_directory, mouse_scale

ROOT = Path(__file__).resolve().parent
LAB = (ROOT.parent.parent / 'work/cemu-lab').resolve()
GAME = None  # Set from ignored local configuration, never from a user-specific source path.
MLC01 = LAB / 'mlc01'
CEMU_EXE = LAB / 'Cemu.exe'
TERRAIN_ASSETS = (ROOT.parent.parent / 'work/terrain-assets/content/Terrain/A').resolve()
PRISM_EXE = Path(os.environ.get('LOCALAPPDATA', '')) / 'SkyCraft/Prism/prismlauncher.exe'
INSTANCE_NAME = 'HyruleCraft-dev'
TEST_PROCESS_JSON = LAB / 'test-process.json'
NATIVE_DIR = native_directory(ROOT)


def get_kernel32():
    """Return kernel32 with explicit 64-bit handle types and prototypes."""
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    k.OpenProcess.restype = W.HANDLE
    k.CloseHandle.argtypes = [W.HANDLE]
    k.CloseHandle.restype = W.BOOL
    k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
    k.QueryFullProcessImageNameW.restype = W.BOOL
    k.GetExitCodeProcess.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]
    k.GetExitCodeProcess.restype = W.BOOL
    k.OpenMutexW.argtypes = [W.DWORD, W.BOOL, W.LPCWSTR]
    k.OpenMutexW.restype = W.HANDLE
    k.CreateMutexW.argtypes = [ctypes.c_void_p, W.BOOL, W.LPCWSTR]
    k.CreateMutexW.restype = W.HANDLE
    return k


def is_process_running(pid, expected_path=None, k=None):
    """Check if process is alive and optionally matches expected binary path."""
    if not isinstance(pid,int) or isinstance(pid,bool) or pid <= 0:
        return False
    if k is None:
        k = get_kernel32()
    # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        exit_code = W.DWORD()
        if not k.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            return False
        if expected_path is not None:
            buf = ctypes.create_unicode_buffer(32768)
            length = W.DWORD(32768)
            if not k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(length)):
                return False
            proc_path = Path(buf.value).resolve()
            exp_path = Path(expected_path).resolve()
            return str(proc_path).lower() == str(exp_path).lower()
        return True
    finally:
        k.CloseHandle(handle)


def validate_cemu_executable(cemu_exe, lab_dir):
    """Ensure target executable is strictly the isolated lab Cemu, never an external install."""
    target = Path(cemu_exe).resolve()
    expected = (Path(lab_dir).resolve() / 'Cemu.exe').resolve()
    if not target.exists():
        raise FileNotFoundError(f"Cemu binary missing: {target}")
    if str(target).lower() != str(expected).lower():
        raise ValueError(f"Target binary {target} does not match isolated lab Cemu {expected}")
    return True


def is_minecraft_dev_instance_running(k=None):
    """Fail-closed check for the specific HyruleCraft-dev Minecraft instance.

    Checks for the unique named mutex Local\\HyruleCraft_v1_minecraft created
    by the Fabric mod, or queries javaw.exe processes matching the instance name
    without dumping account files or command lines.
    """
    if k is None:
        k = get_kernel32()
    # Check named mutex created by SkyLink.announceRunning()
    # SYNCHRONIZE = 0x00100000
    h_mutex = k.OpenMutexW(0x00100000, False, "Local\\HyruleCraft_v1_minecraft")
    if h_mutex:
        k.CloseHandle(h_mutex)
        return True

    # Fallback bounded query: check for javaw with HyruleCraft-dev in commandline
    try:
        cmd = [
            'powershell', '-NoProfile', '-Command',
            "(Get-CimInstance Win32_Process -Filter \"Name='javaw.exe'\") | "
            f"Where-Object {{ $_.CommandLine -like '*{INSTANCE_NAME}*' }} | "
            "Select-Object -ExpandProperty ProcessId"
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return True
    except Exception:
        pass

    return False


def is_duplicate_host_running(current_pid=None, k=None):
    """Use the host's actual singleton; never scan or terminate other Python jobs."""
    k = k or get_kernel32()
    handle = k.OpenMutexW(0x00100000, False, r"Local\HyruleCraft_v1_host")
    if handle:
        k.CloseHandle(handle)
        return True
    error = ctypes.get_last_error()
    if error != 2:  # ERROR_FILE_NOT_FOUND is the only confirmed absence.
        raise OSError(error, 'Cannot establish whether HyruleCraft host is active')
    return False


@contextmanager
def launcher_lease(k=None):
    k = k or get_kernel32()
    handle = k.CreateMutexW(None, False, r"Local\HyruleCraft_v1_launcher")
    error = ctypes.get_last_error()
    if not handle:
        raise OSError(error, 'Cannot reserve HyruleCraft launcher')
    try:
        if error == 183:
            raise RuntimeError('HyruleCraft launcher is already running')
        yield
    finally:
        k.CloseHandle(handle)


def start_cemu(cemu_exe, game_path, mlc01_dir, lab_dir, test_process_json, k=None, fullscreen=False):
    """Launch isolated Cemu or attach to existing verified lab instance with failure propagation."""
    validate_cemu_executable(cemu_exe, lab_dir)
    game = Path(game_path).resolve()
    if not game.exists():
        raise FileNotFoundError(f"Game title.tmd not found: {game}")

    # Check existing process recorded in test-process.json
    proc_json = Path(test_process_json)
    if proc_json.exists():
        try:
            saved_pid = json.loads(proc_json.read_text()).get('pid')
            if saved_pid and is_process_running(saved_pid, cemu_exe, k=k):
                print(f"[+] Attached to existing running lab Cemu (PID {saved_pid}).")
                return saved_pid
        except Exception:
            pass

    print("[*] Launching isolated Cemu 2.6 with Breath of the Wild...")
    proc = subprocess.Popen(
        [str(cemu_exe), '-g', str(game), '-m', str(mlc01_dir)] ,
        cwd=str(lab_dir)
    )

    # Detect immediate crash or launch failure
    time.sleep(0.5)
    exit_code = proc.poll()
    if exit_code is not None:
        raise RuntimeError(f"Isolated Cemu exited immediately with code {exit_code}")

    proc_json.write_text(json.dumps({'pid': proc.pid}))
    print(f"[+] Isolated Cemu started with PID {proc.pid}.")
    return proc.pid


def start_minecraft(prism_exe, instance_name, k=None):
    """Launch Minecraft dev-instance via Prism if not already running."""
    if is_minecraft_dev_instance_running(k=k):
        print("[+] Verified Minecraft dev instance is already active.")
        return True

    prism = Path(prism_exe).resolve()
    if not prism.exists():
        raise FileNotFoundError(f"Prism Launcher missing: {prism}")

    print(f"[*] Starting Minecraft instance '{instance_name}' via Prism...")
    proc = subprocess.Popen([str(prism), '--launch', instance_name])
    time.sleep(0.5)
    exit_code = proc.poll()
    if exit_code is not None and exit_code != 0:
        raise RuntimeError(f"Prism Launcher exited immediately with code {exit_code}")

    # Bounded wait for dev instance identity to become detectable (up to 30s)
    for i in range(30):
        time.sleep(1.0)
        if is_minecraft_dev_instance_running(k=k):
            print("[+] Minecraft dev instance confirmed running.")
            return True
        if (i + 1) % 5 == 0:
            print(f"    [*] Still waiting for Minecraft dev instance to initialize ({i + 1}/30s)...")

    raise RuntimeError('Minecraft dev instance did not become ready; wait for Prism to finish, then retry')


def wait_for_botw_bridge(pid, lab_dir, bridge_module=None, timeout=90, k=None, menu_input=False):
    """Wait for BOTW memory bridge, ensuring handles are closed across retry attempts."""
    if bridge_module is None:
        sys.path.insert(0, str(NATIVE_DIR))
        import bridge
        bridge_module = bridge

    cemu_exe = Path(lab_dir) / 'Cemu.exe'
    log_path = Path(lab_dir) / 'log.txt'
    start_time = time.monotonic()
    last_print = 0
    if menu_input:
        from menu_keys import MenuKeys
        menu_keys=MenuKeys(pid)
    else:
        menu_keys=None

    print("[*] Waiting for BOTW memory bridge to become ready in Cemu...")
    while time.monotonic() - start_time < timeout:
        if not is_process_running(pid, cemu_exe, k=k):
            raise RuntimeError(f"Cemu process (PID {pid}) exited while waiting for bridge.")

        botw = None
        try:
            botw = bridge_module.Process(pid, log_path)
            pos = botw.position()
            eye, direction = botw.view()
            if menu_keys: menu_keys.release(botw)
            print(f"[+] Memory bridge connected! Link position: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
            return True
        except (ValueError, OSError):
            now = time.monotonic()
            if now - last_print > 5:
                print("    [*] Still waiting for gameplay world...")
                last_print = now
            if menu_keys and botw is not None:
                # Poll often enough to retain short taps; each press is held at
                # least150ms in our mailbox so BOTW sees a full native update.
                try:
                    for _ in range(30):
                        menu_keys.update(botw)
                        time.sleep(.01)
                except BaseException:
                    menu_keys.release(botw)
                    raise
                if time.monotonic()-start_time>=timeout: menu_keys.release(botw)
            else:
                time.sleep(0.5)
        finally:
            if botw is not None:
                if menu_keys and sys.exc_info()[0] not in (None,ValueError,OSError): menu_keys.release(botw)
                botw.close(reset_mailbox=False)

    raise TimeoutError(f"Timed out after {timeout}s waiting for BOTW memory bridge.")


def build_host_command(python_exe, root_dir, cemu_pid, log_path, terrain_assets, seconds=86400, no_input=False):
    """Construct command line arguments for host_link.py."""
    cmd = [
        str(python_exe),
        str(Path(root_dir) / 'host_link.py'),
        '--pid', str(cemu_pid),
        '--cemu-log', str(log_path),
        '--renderer',
        '--first-person',
        '--mc-movement',
        '--experimental-heightfield', str(terrain_assets),
        '--seconds', str(seconds)
    ]
    if no_input:
        cmd.append('--no-input')
    return cmd


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='HyruleCraft hardened unified launcher')
    parser.add_argument('--no-input', action='store_true', help='Pass --no-input to host_link for unattended runs')
    parser.add_argument('--recover-home',action='store_true',help='Return to verified clear ground near the house')
    parser.add_argument('--scripted-controls-probe', action='store_true', help='Bounded no-input keyboard movement validation')
    parser.add_argument('--scripted-travel-probe',action='store_true',help='Bounded 32m travel test; requires --no-input')
    parser.add_argument('--mouse-stop-probe',action='store_true',help='Bounded native camera release check; requires --no-input')
    display=parser.add_mutually_exclusive_group()
    display.add_argument('--fullscreen',action='store_true',default=None,help='Start the TV in borderless fullscreen')
    display.add_argument('--windowed',dest='fullscreen',action='store_false',help='Start the TV windowed')
    parser.add_argument('--config',type=Path,help='Local JSON paths/preferences file')
    parser.add_argument('--doctor',action='store_true',help='Read-only setup diagnosis; starts no processes')
    parser.add_argument('--mouse-scale',type=mouse_scale,help='Camera speed multiplier, 0.05 to 2.0')
    parser.add_argument('--bridge-timeout', type=float, default=600, help='Time allowed to load the existing BOTW save')
    parser.add_argument('--seconds', type=float, default=86400, help='Host link duration in seconds')
    args = parser.parse_args(argv)
    if args.scripted_controls_probe and not args.no_input:parser.error('Controls validation requires --no-input')
    if args.scripted_travel_probe and not args.no_input:parser.error('Travel validation requires --no-input')
    if args.mouse_stop_probe and not args.no_input:parser.error('Mouse validation requires --no-input')
    if not 1 <= args.seconds <= 86400:parser.error('Host duration must be between 1 and 86400 seconds')
    if not 1 <= args.bridge_timeout <= 600: parser.error("Bridge timeout must be between 1 and 600 seconds")
    return args


def sync_runtime_artifacts(root_dir, lab_dir, mods_dir, *, minecraft_running, cemu_running, native_dir=None):
    """Install current built artifacts only while their isolated owner is stopped."""
    root_dir, lab_dir, mods_dir = map(Path, (root_dir, lab_dir, mods_dir))
    native_dir=Path(native_dir) if native_dir else native_directory(root_dir)
    artifacts = [
        (root_dir/'dist/HyruleCraft.addon64', lab_dir/'HyruleCraft.addon64', cemu_running),
        (root_dir/'renderer/HyruleCraft.fx', lab_dir/'HyruleCraft.fx', cemu_running),
        (native_dir/'generated/HyruleBlocks/patch_bridge.asm',lab_dir/'graphicPacks/HyruleBlocks/patch_bridge.asm',cemu_running),
        (native_dir/'generated/HyruleBlocks/rules.txt',lab_dir/'graphicPacks/HyruleBlocks/rules.txt',cemu_running),
        (root_dir/'fabric/build/libs/hyrulecraft-0.1.0-botw-dev.jar', mods_dir/'hyrulecraft-0.1.0-botw-dev.jar', minecraft_running),
    ]
    def digest(path):
        return hashlib.sha256(path.read_bytes()).digest() if path.is_file() else None
    for source, _, _ in artifacts:
        if not source.is_file():raise FileNotFoundError(f'Built HyruleCraft artifact missing: {source}')
    pending=[]
    for source, destination, running in artifacts:
        if not source.is_file():
            raise FileNotFoundError(f'Built HyruleCraft artifact missing: {source}')
        if digest(source)==digest(destination):continue
        if running:pending.append(destination);continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        if digest(source)!=digest(destination):raise RuntimeError(f'Artifact copy verification failed: {destination}')
        print(f'[+] Updated {destination.name}',flush=True)
    if pending:
        raise RuntimeError('A newer HyruleCraft build needs its isolated game closed before installation: '+', '.join(p.name for p in pending))


def main(argv=None):
    global LAB,GAME,MLC01,CEMU_EXE,TERRAIN_ASSETS,PRISM_EXE,INSTANCE_NAME,TEST_PROCESS_JSON,NATIVE_DIR
    args = parse_args(argv)
    config=load_config(ROOT,args.config)
    LAB=config['cemu_directory'];GAME=config['game_title'];MLC01=LAB/'mlc01';CEMU_EXE=LAB/'Cemu.exe'
    TERRAIN_ASSETS=config['terrain_directory'];PRISM_EXE=config['prism_executable'];INSTANCE_NAME=config['instance_name']
    TEST_PROCESS_JSON=LAB/'test-process.json';NATIVE_DIR=config['native_directory']
    if args.doctor:
        checks=inspect_setup(ROOT,config)
        for item in checks:print(('OK   ' if item['ok'] else 'MISS ')+item['name']+': '+item['detail'])
        print('Diagnosis starts no game processes and does not read account or save files.')
        return 0 if all(item['ok'] for item in checks) else 1

    print("=" * 66)
    print("           HYRULECRAFT HARDENED UNIFIED LAUNCHER")
    print("=" * 66)

    if is_duplicate_host_running():
        print('[+] HyruleCraft is already running. Use its existing Cemu window.')
        return 0
    checks=inspect_setup(ROOT,config)
    missing=[item['name'] for item in checks if not item['ok']]
    if missing:raise RuntimeError('Setup incomplete: '+', '.join(missing)+'. Run launch.py --doctor.')
    cemu_running=False
    if TEST_PROCESS_JSON.is_file():
        try:saved_pid=json.loads(TEST_PROCESS_JSON.read_text()).get('pid',0)
        except (ValueError,OSError):saved_pid=0
        cemu_running=is_process_running(saved_pid,CEMU_EXE)
    sync_runtime_artifacts(ROOT,LAB,
        PRISM_EXE.parent/'instances'/INSTANCE_NAME/'.minecraft/mods',
        minecraft_running=is_minecraft_dev_instance_running(),cemu_running=cemu_running,native_dir=NATIVE_DIR)

    # 1. Start Minecraft dev-instance
    if not start_minecraft(PRISM_EXE, INSTANCE_NAME):
        raise RuntimeError('Minecraft dev-instance readiness was not verified')

    # 2. Start Cemu
    cemu_pid = start_cemu(CEMU_EXE, GAME, MLC01, LAB, TEST_PROCESS_JSON, fullscreen=args.fullscreen)

    # 3. Wait for memory bridge
    print("In BOTW: Enter = confirm, arrows = choose, Backspace = back.")
    print("Load Continue -> existing Great Plateau save -> Start. PC controls engage automatically in-world!")
    wait_for_botw_bridge(cemu_pid, LAB, timeout=args.bridge_timeout, menu_input=not args.no_input)
    if not args.no_input:
        try:
            u32 = ctypes.windll.user32
            cemu_win = None
            def _find_cemu_win(hwnd, _):
                nonlocal cemu_win
                wpid = ctypes.wintypes.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value == cemu_pid and u32.IsWindowVisible(hwnd):
                    cemu_win = hwnd
                    return False
                return True
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            u32.EnumWindows(EnumProc(_find_cemu_win), 0)
            if cemu_win:
                u32.SetForegroundWindow(cemu_win)
        except Exception:
            pass

    # 4. Launch host_link
    host_cmd = build_host_command(
        sys.executable, ROOT, cemu_pid, LAB / 'log.txt', TERRAIN_ASSETS,
        seconds=args.seconds, no_input=args.no_input
    )

    host_cmd.extend(['--native-directory',str(NATIVE_DIR),'--mouse-scale',str(args.mouse_scale if args.mouse_scale is not None else config['mouse_scale'])])
    if config['invert_y']:host_cmd.append('--invert-y')
    if args.fullscreen if args.fullscreen is not None else config['fullscreen']:host_cmd.append('--fullscreen')
    if args.scripted_controls_probe:host_cmd.append('--scripted-controls-probe')
    if args.scripted_travel_probe:host_cmd.append('--scripted-travel-probe')
    if args.mouse_stop_probe:host_cmd.append('--mouse-stop-probe')
    if args.recover_home:host_cmd.append('--recover-home')
    print("-" * 66)
    print("[*] Starting host link bridge...")
    if args.no_input:
        print("    Mode: unattended observation (--no-input)")
    else:
        print("    Mode: interactive input passthrough enabled")

    print("-" * 66)

    try:
        return subprocess.run(host_cmd, cwd=str(ROOT)).returncode
    except KeyboardInterrupt:
        print("\n[+] HyruleCraft launcher stopped by user.")
        return 130


if __name__ == '__main__':
    try:
        if '--doctor' in sys.argv:
            sys.exit(main())
        with launcher_lease():sys.exit(main())
    except (ValueError,OSError,RuntimeError,TimeoutError) as error:
        print('HyruleCraft: '+str(error),file=sys.stderr)
        sys.exit(1)
