"""Read-only BOTW terrain asset decoder; world transform is a candidate, not live collision.
No memory writes or player-release API. Game assets stay in the local scratch directory.
TSCB record layout reference: https://github.com/zephenryus/botw-tools/blob/develop/tools/terrain/tscb.py
"""
from dataclasses import dataclass
import hashlib, math, struct

@dataclass(frozen=True)
class Tile:
    name: str
    x: float
    z: float
    size: float
    minimum: float
    maximum: float

@dataclass(frozen=True)
class Scene:
    horizontal_scale: float
    height_range: float
    tiles: tuple

    @classmethod
    def decode(cls, data):
        if len(data)<52 or data[:4]!=b'TSCB' or struct.unpack_from('<I',data,4)[0]!=10:
            raise ValueError('Unsupported TSCB header/version')
        horizontal,height=struct.unpack_from('>ff',data,16)
        count=struct.unpack_from('>I',data,28)[0]
        table=48+struct.unpack_from('>I',data,48)[0]
        if count>100000 or table<52 or table+count*4>len(data):
            raise ValueError('Invalid tile table')
        if not all(math.isfinite(v) and v>0 for v in (horizontal,height)):
            raise ValueError('Invalid scene scales')
        tiles=[]
        for i in range(count):
            p=table+i*4;o=p+struct.unpack_from('>I',data,p)[0]
            if o+48>len(data):raise ValueError('Invalid tile record')
            x,z,size,minimum,maximum=struct.unpack_from('>5f',data,o)
            if not all(math.isfinite(v) for v in (x,z,size,minimum,maximum)) or size<=0 or not 0<=minimum<=maximum<=1:
                raise ValueError('Invalid tile values')
            nameoff=o+32+struct.unpack_from('>I',data,o+32)[0]
            end=data.find(b'\0',nameoff,nameoff+32)
            if nameoff<o or end<0:raise ValueError('Invalid tile name')
            name=data[nameoff:end].decode('ascii')
            if len(name)!=10 or any(c not in '0123456789ABCDEFabcdef' for c in name):
                raise ValueError('Unsupported terrain tile name')
            tiles.append(Tile(name,x,z,size,minimum,maximum))
        return cls(horizontal,height,tuple(tiles))

class Heightfield:
    def __init__(self, scene, tile, raw):
        if len(raw)!=256*256*2:raise ValueError('Expected 256x256 uint16 heightfield')
        self.scene,self.tile=scene,tile
        self.samples=struct.unpack('<65536H',raw)
        self.sha256=hashlib.sha256(raw).hexdigest()
        # Wii U container/header is big-endian; this payload is little-endian.
        if abs(min(self.samples)/65535-tile.minimum)>2/65535 or abs(max(self.samples)/65535-tile.maximum)>2/65535:
            raise ValueError('Height extrema disagree with scene: wrong tile/byte order/data')
        self.step=tile.size*scene.horizontal_scale/256
        self.origin=((tile.x-tile.size/2)*scene.horizontal_scale,(tile.z-tile.size/2)*scene.horizontal_scale)

    def vertex_candidate(self, x, z):
        if not 0<=x<256 or not 0<=z<256:raise ValueError('Sample outside authenticated tile')
        return (self.origin[0]+x*self.step,self.samples[z*256+x]*self.scene.height_range/65535,self.origin[1]+z*self.step)

    def height_candidate(self,x,z):
        gx=(x-self.origin[0])/self.step;gz=(z-self.origin[1])/self.step
        if not 0<=gx<255 or not 0<=gz<255:raise ValueError('No authenticated cell at tile edge/outside tile')
        ix,iz=math.floor(gx),math.floor(gz);fx,fz=gx-ix,gz-iz
        h00=self.vertex_candidate(ix,iz)[1];h10=self.vertex_candidate(ix+1,iz)[1]
        h01=self.vertex_candidate(ix,iz+1)[1];h11=self.vertex_candidate(ix+1,iz+1)[1]
        # Bilinear diagnostic only; Havok cell diagonal has not been established.
        return (h00*(1-fx)+h10*fx)*(1-fz)+(h01*(1-fx)+h11*fx)*fz

    def triangles_candidate(self, min_x,min_z,max_x,max_z):
        # Reject incomplete crops. Missing neighbours must never become known-empty collision.
        for x,z in ((min_x,min_z),(max_x,max_z)):
            self.height_candidate(x,z)
        x0=math.floor((min_x-self.origin[0])/self.step);x1=math.ceil((max_x-self.origin[0])/self.step)
        z0=math.floor((min_z-self.origin[1])/self.step);z1=math.ceil((max_z-self.origin[1])/self.step)
        if x0>=x1 or z0>=z1:raise ValueError('Empty crop')
        for z in range(z0,z1):
            for x in range(x0,x1):
                a=self.vertex_candidate(x,z);b=self.vertex_candidate(x+1,z)
                c=self.vertex_candidate(x,z+1);d=self.vertex_candidate(x+1,z+1)
                # Upward winding in Y-up coordinates. Diagonal still requires native verification.
                yield (a,c,b)
                yield (b,c,d)

class StitchedHeightfield:
    """One authenticated lattice spanning equal-resolution adjacent tiles."""
    def __init__(self, fields):
        if not fields:raise ValueError('No authenticated terrain tiles')
        self.origin,self.step=fields[0].origin,fields[0].step
        self.fields={}
        for field in fields:
            if not math.isclose(field.step,self.step,rel_tol=0,abs_tol=1e-9):raise ValueError('Mixed terrain resolutions')
            offset=tuple((v-o)/(256*self.step) for v,o in zip(field.origin,self.origin))
            if any(abs(v-round(v))>1e-7 for v in offset):raise ValueError('Misaligned terrain lattice')
            key=tuple(round(v) for v in offset)
            if key in self.fields:raise ValueError('Duplicate terrain tile')
            self.fields[key]=field

    def vertex_candidate(self,x,z):
        tx,ix=divmod(x,256);tz,iz=divmod(z,256)
        field=self.fields.get((tx,tz))
        if field is None:raise ValueError('Missing authenticated terrain neighbour')
        return field.vertex_candidate(ix,iz)

    def height_candidate(self,x,z):
        gx=(x-self.origin[0])/self.step;gz=(z-self.origin[1])/self.step
        ix,iz=math.floor(gx),math.floor(gz);fx,fz=gx-ix,gz-iz
        a=self.vertex_candidate(ix,iz)[1];b=self.vertex_candidate(ix+1,iz)[1]
        c=self.vertex_candidate(ix,iz+1)[1];d=self.vertex_candidate(ix+1,iz+1)[1]
        return (a*(1-fx)+b*fx)*(1-fz)+(c*(1-fx)+d*fx)*fz

    def triangles_candidate(self,min_x,min_z,max_x,max_z):
        x0=math.floor((min_x-self.origin[0])/self.step);x1=math.ceil((max_x-self.origin[0])/self.step)
        z0=math.floor((min_z-self.origin[1])/self.step);z1=math.ceil((max_z-self.origin[1])/self.step)
        if x0>=x1 or z0>=z1:raise ValueError('Empty crop')
        for z in range(z0,z1):
            for x in range(x0,x1):
                a=self.vertex_candidate(x,z);b=self.vertex_candidate(x+1,z)
                c=self.vertex_candidate(x,z+1);d=self.vertex_candidate(x+1,z+1)
                yield a,c,b
                yield b,c,d
