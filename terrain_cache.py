"""Read owned heightfield packs into the isolated cache; never edit game assets."""
from pathlib import Path
import re
import struct
import subprocess
import sys
from terrain_assets import Heightfield

from runtime_config import load_config
PROJECT=Path(__file__).resolve().parent
ROOT=PROJECT.parents[1]
CONFIG=load_config(PROJECT)
CACHE=CONFIG['terrain_directory']
SOURCE=CONFIG['game_title'].parent if CONFIG['game_title'] else None



def decode_pack(raw):
    if len(raw)<16 or raw[:4]!=b'Yaz0':raise ValueError('Invalid heightfield pack')
    size=struct.unpack_from('>I',raw,4)[0]
    if not 0<size<=2*1024*1024:raise ValueError('Oversized heightfield pack')
    out=bytearray();i=16
    while len(out)<size:
        code=raw[i];i+=1
        for bit in range(7,-1,-1):
            if len(out)>=size:break
            if code&(1<<bit):out.append(raw[i]);i+=1
            else:
                a,b=raw[i:i+2];i+=2;distance=((a&15)<<8|b)+1;n=a>>4
                if n==0:n=raw[i]+18;i+=1
                else:n+=2
                if distance>len(out) or len(out)+n>size:raise ValueError('Invalid Yaz0 backreference')
                for _ in range(n):out.append(out[-distance])
    data=bytes(out)
    if data[:4]!=b'SARC' or data[6:8] not in (b'\xfe\xff',b'\xff\xfe'):raise ValueError('Invalid SARC')
    endian='>' if data[6:8]==b'\xfe\xff' else '<'
    def u16(o):return struct.unpack_from(endian+'H',data,o)[0]
    def u32(o):return struct.unpack_from(endian+'I',data,o)[0]
    if u32(8)!=len(data):raise ValueError('SARC size mismatch')
    start=u16(4);count=u16(start+6);nodes=start+u16(start+4);names=nodes+count*16
    if count>16 or data[start:start+4]!=b'SFAT' or data[names:names+4]!=b'SFNT':raise ValueError('Invalid heightfield table')
    result={}
    for j in range(count):
        node=nodes+j*16;attr=u32(node+4);begin=u32(node+8);end=u32(node+12)
        if not attr>>24:raise ValueError('Unnamed heightfield')
        namepos=names+u16(names+4)+(attr&0xffffff)*4
        nameend=data.find(b'\0',namepos,namepos+32)
        if nameend<0:raise ValueError('Invalid heightfield name')
        name=data[namepos:nameend].decode('ascii')
        if not re.fullmatch(r'[0-9A-Fa-f]{10}\.hght',name):raise ValueError('Unsafe heightfield name')
        base=u32(12)
        if end-begin!=131072 or base+end>len(data):raise ValueError('Invalid heightfield length')
        result[name]=data[base+begin:base+end]
    return result


def ensure_heightfield(assets,scene,tile):
    assets=Path(assets)
    target=assets/'MainField'/(tile.name+'.hght')
    if target.exists():return
    # Extraction is restricted to this project's known isolated cache.
    if assets.resolve()!=CACHE.resolve():raise FileNotFoundError(target)
    if not re.fullmatch(r'[0-9A-Fa-f]{10}',tile.name):raise ValueError('Invalid tile name')
    group=tile.name[:-1]+format(int(tile.name[-1],16)&~3,'X')
    pack=assets/'MainField'/(group+'.hght.sstera')
    if not pack.exists():
        if SOURCE is None or not (ROOT/'work/extract_crate.py').is_file():
            raise FileNotFoundError('Missing owned terrain tile '+tile.name+'. Prepare the authentic terrain cache before travel.')
        pattern=r'^content/Terrain/A/MainField/'+group+r'\.hght(?:\.sstera)?$'
        run=subprocess.run([sys.executable,str(ROOT/'work/extract_crate.py'),str(SOURCE),pattern,
                            str(ROOT/'work/terrain-assets')],cwd=ROOT,capture_output=True,timeout=30)
        if run.returncode:raise RuntimeError('Owned heightfield extraction failed')
    if pack.exists():
        tiles={t.name:t for t in scene.tiles}
        decoded=decode_pack(pack.read_bytes())
        # Authenticate all payloads before writing any decoded tile.
        for name,payload in decoded.items():Heightfield(scene,tiles[name[:-5]],payload)
        for name,payload in decoded.items():
            dest=pack.parent/name
            if not dest.exists():dest.write_bytes(payload)
    if not target.exists():raise FileNotFoundError('Owned resource does not supply tile '+tile.name)
