"""Local paths and player preferences; never contain login/account data."""
import json, math, os, re
from pathlib import Path

def native_directory(root):
    root=Path(root)
    return root/'native' if (root/'native/bridge.py').is_file() else root.parent/'HyruleBlocks'

def mouse_scale(value):
    if isinstance(value,bool):raise ValueError('mouse_scale must be a number')
    try:value=float(value)
    except (TypeError,ValueError):raise ValueError('mouse_scale must be a number') from None
    if not math.isfinite(value) or not .05<=value<=2:raise ValueError('mouse_scale must be between 0.05 and 2.0')
    return value

def load_config(root, path=None):
    root=Path(root).resolve();file=Path(path).resolve() if path else root/'hyrulecraft.local.json'
    if path is not None and not file.is_file():raise FileNotFoundError('Requested configuration file does not exist')
    data=json.loads(file.read_text(encoding='utf-8-sig')) if file.is_file() else {}
    if not isinstance(data,dict):raise ValueError('Configuration must be a JSON object')
    defaults={'cemu_directory':str(root.parent.parent/'work/cemu-lab'),
              'terrain_directory':str(root.parent.parent/'work/terrain-assets/content/Terrain/A'),
              'prism_executable':str(Path(os.environ.get('LOCALAPPDATA',''))/'SkyCraft/Prism/prismlauncher.exe'),
              'native_directory':str(native_directory(root)), 'game_title':'',
              'instance_name':'HyruleCraft-dev','mouse_scale':.5,'fullscreen':True,'invert_y':False}
    unknown=set(data)-set(defaults)
    if unknown:raise ValueError('Unknown configuration keys: '+', '.join(sorted(unknown)))
    config=defaults|data
    for key in ('cemu_directory','terrain_directory','prism_executable','native_directory','game_title'):
        value=config[key]
        if not isinstance(value,str):raise ValueError(key+' must be a path string')
        if not value.strip():
            if key!='game_title':raise ValueError(key+' cannot be blank')
            config[key]=None;continue
        target=Path(os.path.expandvars(value)).expanduser()
        config[key]=(target if target.is_absolute() else file.parent/target).resolve()
    name=config['instance_name']
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',name):
        raise ValueError('instance_name must be a simple Prism instance name')
    config['mouse_scale']=mouse_scale(config['mouse_scale'])
    for key in ('fullscreen','invert_y'):
        if not isinstance(config[key],bool):raise ValueError(key+' must be true or false')
    return config

def inspect_setup(root, config):
    root=Path(root);lab=config['cemu_directory'];native=config['native_directory']
    checks=[]
    def check(name,path,directory=False):
        ok=bool(path and (path.is_dir() if directory else path.is_file()))
        checks.append({'name':name,'ok':ok,'detail':'ready' if ok else 'missing; configure or build this dependency'})
    check('Isolated Cemu',lab/'Cemu.exe' if lab else None)
    check('BOTW title.tmd',config['game_title'])
    check('Authentic terrain directory',config['terrain_directory'],True)
    check('Prism launcher',config['prism_executable'])
    prism=config['prism_executable'];instance=prism.parent/'instances'/config['instance_name'] if prism else None
    check('Separate Minecraft instance',instance,True)
    check('Fabric instance components',instance/'mmc-pack.json' if instance else None)
    check('Native bridge',native/'bridge.py' if native else None)
    for name,path in [('Native patch',native/'generated/HyruleBlocks/patch_bridge.asm' if native else None),
                      ('Native rules',native/'generated/HyruleBlocks/rules.txt' if native else None),
                      ('Renderer addon',root/'dist/HyruleCraft.addon64'),
                      ('Renderer shader',root/'renderer/HyruleCraft.fx'),
                      ('Fabric mod',root/'fabric/build/libs/hyrulecraft-0.1.0-botw-dev.jar')]:check(name,path)
    return checks
