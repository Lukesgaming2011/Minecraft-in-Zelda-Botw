"""Prepare authentic heightfield-only collision packets offline.
This does not establish Havok parity or cover objects, caves, bridges or water.
"""
import math
from pathlib import Path
from terrain_assets import Scene,Heightfield,StitchedHeightfield
from collaboration.terrain_export import ColTri,TRI_TERRAIN,REGION_SIZE,TerrainStreamer

def prepare_heightfield(asset_directory,position,*,radius_regions=1,require_ground_match=True):
    if radius_regions not in (1,2):raise ValueError("Unsupported terrain preload radius")
    if not all(math.isfinite(v) for v in position):raise ValueError("Non-finite terrain position")
    assets=Path(asset_directory)
    scene=Scene.decode((assets/'MainField.tscb').read_bytes())
    px,py,pz=position
    candidates=[t for t in scene.tiles if (t.x-t.size/2)*scene.horizontal_scale<=px<(t.x+t.size/2)*scene.horizontal_scale and (t.z-t.size/2)*scene.horizontal_scale<=pz<(t.z+t.size/2)*scene.horizontal_scale]
    if not candidates:raise ValueError('No terrain metadata at player position')
    tile=min(candidates,key=lambda t:t.size)
    from terrain_cache import ensure_heightfield
    ensure_heightfield(assets,scene,tile)
    raw=(assets/'MainField'/(tile.name+'.hght')).read_bytes()
    field=Heightfield(scene,tile,raw)
    rx,ry,rz=(math.floor(v/REGION_SIZE) for v in position)
    min_x,min_z=(rx-radius_regions)*REGION_SIZE,(rz-radius_regions)*REGION_SIZE
    max_x,max_z=(rx+radius_regions+1)*REGION_SIZE,(rz+radius_regions+1)*REGION_SIZE
    # Load equal-resolution neighbours intersecting the footprint plus one sample.
    # Missing files or seam vertices fail before any ready region is published.
    neighbours=[field]
    margin=field.step
    for t in scene.tiles:
        if t.name==tile.name or t.size!=tile.size:continue
        half=t.size*scene.horizontal_scale/2
        cx,cz=t.x*scene.horizontal_scale,t.z*scene.horizontal_scale
        if cx+half<=min_x-margin or cx-half>max_x+margin or cz+half<=min_z-margin or cz-half>max_z+margin:continue
        ensure_heightfield(assets,scene,t)
        neighbours.append(Heightfield(scene,t,(assets/'MainField'/(t.name+'.hght')).read_bytes()))
    stitched=StitchedHeightfield(neighbours)
    native_height_error=py-stitched.height_candidate(px,pz)
    if require_ground_match and abs(native_height_error)>0.2:raise ValueError('Player does not match heightfield ground; object/water/airborne or transform mismatch')
    triangles=[ColTri(a,b,c,TRI_TERRAIN) for a,b,c in stitched.triangles_candidate(min_x,min_z,max_x,max_z)]
    return triangles,{'tile':tile.name,'sha256':field.sha256,'tiles':[{'name':f.tile.name,'sha256':f.sha256} for f in neighbours],'position':position,'native_height_error':native_height_error,'ground_match_required':require_ground_match,'triangle_count':len(triangles),'footprint':[min_x,min_z,max_x,max_z],'coverage':'heightfield only; native objects and Havok parity unverified'}
