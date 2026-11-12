"""Concise read-only runtime health. Does not attach to a game or capture input."""
import json,time
from pathlib import Path

def summarize(path,now=None):
    path=Path(path);now=time.time() if now is None else now
    try:
        age=max(0,now-path.stat().st_mtime);data=json.loads(path.read_text())
    except (OSError,ValueError):return {'live':False,'phase':'no readable status','age_seconds':None}
    if not isinstance(data,dict):return {'live':False,'phase':'invalid status object','age_seconds':round(age,1)}
    live=age<=5 and data.get('phase')=='live-minecraft-renderer'
    return {'live':live,'phase':data.get('phase','unknown'),'age_seconds':round(age,1),
            'terrain_ready':bool(data.get('terrain_collision_ready')),
            'movement':data.get('movement_authority','BOTW'),
            'input_allowed':bool(data.get('input_capture_allowed')),
            'captured':bool(data.get('mouse_diagnostics',{}).get('captured')),
            'terrain_collision_complete':False}
if __name__=='__main__':
    status=summarize(Path(__file__).resolve().parent/'link-status.json')
    for key,value in status.items():print(f'{key}: {value}')
