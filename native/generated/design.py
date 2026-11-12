# Generated from sheets; edit the sheets first.
from types import SimpleNamespace
BLOCKS = {
    'wood': SimpleNamespace(**{'id': 'wood', 'label': 'Wood (BOTW placeholder)', 'actor': 'Kibako_Contain_01', 'grid': 2.0, 'half_extent': 1.0, 'pivot_to_center_y': 1.0, 'limit': 32}),
}
SYSTEMS = {
    'creative': SimpleNamespace(**{'id': 'creative', 'mode': 'solo', 'inventory': 'unlimited', 'persistence': 'session-only', 'target': 'botw-v208'}),
    'hud': SimpleNamespace(**{'id': 'hud', 'mode': 'overlay', 'inventory': 'nine-slot', 'persistence': 'session-only', 'target': 'botw-v208'}),
    'first-person': SimpleNamespace(**{'id': 'first-person', 'mode': 'camera-distance-zero', 'inventory': 'unchanged', 'persistence': 'session-only', 'target': 'botw-v208'}),
    'mouse-capture': SimpleNamespace(**{'id': 'mouse-capture', 'mode': 'foreground-building-clicks', 'inventory': 'clicks-consumed', 'persistence': 'session-only', 'target': 'botw-v208'}),
    'block-textures': SimpleNamespace(**{'id': 'block-textures', 'mode': 'local-resource-replacement', 'inventory': 'slot-1-pixel-planks', 'persistence': 'lab-pack', 'target': 'botw-v208'}),
}
CONTROLS = {
    'place': SimpleNamespace(**{'id': 'place', 'keyboard': 'RMB', 'controller': 'ZR', 'system': 'creative'}),
    'break': SimpleNamespace(**{'id': 'break', 'keyboard': 'LMB', 'controller': 'ZL', 'system': 'creative'}),
    'move': SimpleNamespace(**{'id': 'move', 'keyboard': 'WASD', 'controller': 'left-stick', 'system': 'creative'}),
    'look': SimpleNamespace(**{'id': 'look', 'keyboard': 'mouse', 'controller': 'right-stick', 'system': 'creative'}),
    'jump': SimpleNamespace(**{'id': 'jump', 'keyboard': 'Space', 'controller': 'X', 'system': 'creative'}),
    'inventory': SimpleNamespace(**{'id': 'inventory', 'keyboard': 'E', 'controller': 'minus', 'system': 'hud'}),
    'slot': SimpleNamespace(**{'id': 'slot', 'keyboard': '1-9', 'controller': 'D-pad-left/right', 'system': 'hud'}),
    'build-toggle': SimpleNamespace(**{'id': 'build-toggle', 'keyboard': 'F6', 'controller': 'D-pad-up', 'system': 'creative'}),
    'perspective': SimpleNamespace(**{'id': 'perspective', 'keyboard': 'F5', 'controller': 'D-pad-down', 'system': 'first-person'}),
    'menu': SimpleNamespace(**{'id': 'menu', 'keyboard': 'Enter/Backspace/arrows (building off)', 'controller': 'A/B/D-pad', 'system': 'hud'}),
}
TEXTURES = {
    'pixel-planks': SimpleNamespace(**{'id': 'pixel-planks', 'block': 'wood', 'size': 16, 'palette': ['#9f713b', '#a77a43', '#b88749', '#956735', '#76502b'], 'seed': 410, 'resource': 'Obj_BoxWood_A.Tex1.sbfres', 'surface': 'Obj_BoxWood_A_01_Alb', 'source': 'original-procedural-art', 'repeat': 4}),
}
TARGET = {
    'botw-v208': SimpleNamespace(**{'id': 'botw-v208', 'module': '0x6267bfd0', 'title': '00050000101C9400', 'version': 208, 'evidence': 'Cemu log and installed V208 community patches'}),
}
HOOKS = {
    'tick': SimpleNamespace(**{'id': 'tick', 'address': '0x030d9f48', 'evidence': 'installed BetterVR VPADRead frame input hook: 0x030d9f48; previous SpawnActors tick ran only once in local test'}),
    'create': SimpleNamespace(**{'id': 'create', 'address': '0x037b6040', 'evidence': 'S41L0R/SpawnActors: 0x037b6040'}),
    'new-actor': SimpleNamespace(**{'id': 'new-actor', 'address': '0x037b7698', 'evidence': 'installed BetterVR patch_CTRL_NewActorHook.asm: 0x037b7698'}),
    'delete': SimpleNamespace(**{'id': 'delete', 'address': '0x0378a374', 'evidence': 'wiixlaunch-botw actor.hpp Delete: 0x0378a374'}),
    'input': SimpleNamespace(**{'id': 'input', 'address': '0x030d9f48', 'evidence': 'installed BetterVR patch_CTRL_ButtonInput.asm: 0x030d9f48'}),
    'actor-update': SimpleNamespace(**{'id': 'actor-update', 'address': '0x024adac8', 'evidence': 'wiixlaunch-botw SpawnFlushHook 0x024adac8; local process confirms prologue 0x9421ff50 (stwu r1,-0xb0)'}),
    'camera': SimpleNamespace(**{'id': 'camera', 'address': '0x02b966a4', 'evidence': 'installed BetterVR CameraChase hook 0x02b966a4; local process confirms original mr r3,r31 (0x7fe3fb78)'}),
    'camera-distance': SimpleNamespace(**{'id': 'camera-distance', 'address': '0x02e5feb8', 'evidence': 'BetterVR patch_FirstPersonMode 0x02e5feb8; live v208 original words 3d201021 3d801021 c1a96594 c18c6598 verified'}),
    'player-tick': SimpleNamespace(**{'id': 'player-tick', 'address': '0x02d67cf4', 'evidence': 'wiixlaunch-botw PlayerTickHook 0x02d67cf4; verified live US v208 original prologue 7c0802a6 9421fff0 93e1000c 90010014; 2026-10-05 live Link vtable0x101e5ffc+0x2A4 resolves to 0x02d67cf4 (updateMtxFromPhysics); wrapper preserves original call and corrects after return'}),
    'camera-final-a': SimpleNamespace(**{'id': 'camera-final-a', 'address': '0x02c054fc', 'evidence': 'BetterVR patch_CTRL_CameraControls.asm 0x02c054fc; isolated live US v208 PID10580 on 2026-10-06 original d01f05cc (stfs f0,0x5cc(r31)); ActCamera finalCamMtx+0x5c0 verified local type'}),
    'camera-final-b': SimpleNamespace(**{'id': 'camera-final-b', 'address': '0x02c05590', 'evidence': 'BetterVR patch_CTRL_CameraControls.asm 0x02c05590; isolated live US v208 PID10580 on 2026-10-06 original d1bf05c4 (stfs f13,0x5c4(r31)); ActCamera finalCamMtx+0x5c0 verified local type'}),
    'actor-opacity': SimpleNamespace(**{'id': 'actor-opacity', 'address': '0x037b13ac', 'evidence': 'BetterVR patch_FirstPersonMode.asm Actor::setOpacity at 0x037b13ac; isolated live US v208 PID16896 on2026-10-06 verified seven words c003033c fc000800 4d820020 d023033c 38000001 98030436 4e800020 (load float33c, compare f1, conditional return, store float33c, dirty byte436, return).'}),
}
FIELDS = {
    'camera-singleton': SimpleNamespace(**{'id': 'camera-singleton', 'offset': '0x1046cf88', 'evidence': 'installed BetterVR Camera__sInstance 0x1046cf88; live v208 verified singleton and camera position'}),
    'camera-buffer': SimpleNamespace(**{'id': 'camera-buffer', 'offset': 212, 'evidence': 'live v208 PPC Camera__getLookAtCamera 0x03191b70 adds 0x14 then 0xc0; buffer index+4 and pointers+8'}),
    'player-singleton': SimpleNamespace(**{'id': 'player-singleton', 'offset': '0x10463f38', 'evidence': 'installed BetterVR and wiixlaunch-botw: 0x10463f38'}),
    'player-pointer': SimpleNamespace(**{'id': 'player-pointer', 'offset': 48, 'evidence': 'wiixlaunch-botw symbols: PlayerInfo +0x30'}),
    'position-x': SimpleNamespace(**{'id': 'position-x', 'offset': 516, 'evidence': 'wiixlaunch-botw actor-transforms.md: Actor+0x204'}),
    'position-y': SimpleNamespace(**{'id': 'position-y', 'offset': 532, 'evidence': 'wiixlaunch-botw actor-transforms.md: Actor+0x214'}),
    'position-z': SimpleNamespace(**{'id': 'position-z', 'offset': 548, 'evidence': 'wiixlaunch-botw actor-transforms.md: Actor+0x224'}),
}
