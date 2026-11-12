"""Read and validate the live Wii U US v208 gameplay projection; never write game memory."""
import math
import struct

def decode_projection(raw):
    if len(raw)!=0xb8 or struct.unpack_from('>I',raw,0x90)[0]!=0x1027b54c:
        raise ValueError('Unexpected v208 perspective projection')
    scale,offset=struct.unpack_from('>2f',raw,0x88)
    if (scale,offset)!=(1.,0.):raise ValueError('Unsupported device depth transform')
    near,far,fov,sin,cos,tan,aspect,ox,oy=struct.unpack_from('>9f',raw,0x94)
    matrix=struct.unpack_from('>16f',raw,4)
    if not all(math.isfinite(x) for x in (near,far,fov,sin,cos,tan,aspect,ox,oy,*matrix)):
        raise ValueError('Nonfinite camera projection')
    if not(.01<=near<=10 and 100<=far<=100000 and near<far and .1<fov<3 and .5<aspect<4):
        raise ValueError('Invalid camera projection range')
    expected={0:1/(math.tan(fov/2)*aspect),5:1/math.tan(fov/2),10:-(far+near)/(far-near),11:-2*far*near/(far-near),14:-1}
    if any(not math.isclose(matrix[i],v,rel_tol=1e-4,abs_tol=1e-5) for i,v in expected.items()):
        raise ValueError('Gameplay projection matrix disagrees with scalar fields')
    if abs(ox)>1e-5 or abs(oy)>1e-5:
        raise ValueError('Asymmetric camera projection is unsupported')
    return {'near':near,'far':far,'fov':math.degrees(fov),'aspect':aspect}

def read_projection(process):
    owner=struct.unpack('>I',process.read(process.base+0x1046cf88,4))[0]
    if not 0x10000000<=owner<0xe0000000:raise ValueError('No gameplay camera')
    # Live-verified embedded perspective object at singleton+0x1c. Validate its
    # exact v208 class and matrix each time; the nearby unused GamePad object is rejected.
    return decode_projection(process.read(process.base+owner+0x1c,0xb8))
