"""Background authentic terrain preparation; the host alone publishes packets.
Unknown terrain stays blocked. Existing collision is never cleared on travel.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import math
from functools import partial
import struct
import time
from terrain_stream import prepare_heightfield
from collaboration.terrain_export import (REGION_SIZE, ColRegion, COL_CLEAR,
    COL_TRIS, COL_REGION, COL_FORGET, voxelize_region_triangles)


def region_at(position):
    if len(position)!=3 or not all(math.isfinite(v) for v in position):
        raise ValueError('Invalid terrain position')
    return tuple(math.floor(v/REGION_SIZE) for v in position)


def prepare_batch(assets, position, known, epoch, first, *, ground_anchor=None):
    center=region_at(position)
    regions=set((center[0]+x,center[1]+y,center[2]+z)
                for x,y,z in product(range(-2,3),range(-2,2),range(-2,3))) - set(known)
    if not regions:return [],None
    anchor_report=None
    if first and ground_anchor is not None:
        _,anchor_report=prepare_heightfield(assets,ground_anchor)
    triangles,report=prepare_heightfield(assets,position,radius_regions=2,
                                       require_ground_match=first and anchor_report is None)
    if anchor_report is not None:
        report['ground_validation_anchor']=anchor_report
    # Bucket authenticated triangles once, rather than scanning them 75 times.
    buckets={r:[] for r in regions}
    for tri in triangles:
        lows=[math.floor(min(p[a] for p in (tri.p0,tri.p1,tri.p2))/REGION_SIZE) for a in range(3)]
        highs=[math.floor(max(p[a] for p in (tri.p0,tri.p1,tri.p2))/REGION_SIZE) for a in range(3)]
        # Include triangles lying exactly on a region's upper face.
        for a in range(3):
            v=min(p[a] for p in (tri.p0,tri.p1,tri.p2))
            if v==lows[a]*REGION_SIZE:lows[a]-=1
        spans=[range(max(lows[a],center[a]-2),
                     min(highs[a],center[a]+(1 if a==1 else 2))+1) for a in range(3)]
        for r in product(*spans):
            if r in buckets:buckets[r].append(tri)
    packets=[]
    if first:packets.append((COL_CLEAR,struct.pack('<I',epoch),None))
    for r,tris in sorted(buckets.items(),key=lambda item:sum(abs(a-b) for a,b in zip(item[0],center))):
        rx,ry,rz=r
        blocks=voxelize_region_triangles(rx,ry,rz,tris)
        def header(count):
            return ColRegion(rx*8,ry*8,rz*8,rx*8+7,ry*8+7,rz*8+7,epoch,count).pack()
        packets.append((COL_TRIS,header(len(tris))+b''.join(t.pack() for t in tris),None))
        packets.append((COL_REGION,header(len(blocks))+b''.join(b.pack() for b in blocks),r))
    report.update(epoch=epoch,prepared_regions=len(regions),experimental=True)
    return packets,report


class DynamicTerrain:
    def __init__(self,assets,writer,*,prepare=prepare_batch,executor=None,max_regions=4096,ground_anchor=None):
        self.assets=assets;self.writer=writer;self.prepare=partial(prepare,ground_anchor=ground_anchor) if ground_anchor is not None else prepare
        self.executor=executor or ProcessPoolExecutor(max_workers=1)
        self.known=set();self.pending=deque();self.future=None
        self.epoch=1;self.started=False;self.closed=False;self.retry_at=0
        self.max_regions=max_regions;self.report={'phase':'waiting','coverage':'heightfield only; objects/water/caves unverified'}

    def tick(self,position,now=None):
        if self.closed:return self.report
        now=time.monotonic() if now is None else now
        if self.future is not None and self.future.done():
            try:
                packets,report=self.future.result()
                self.pending.extend(packets)
                if report:self.report=report
                self.report['phase']='publishing'
            except Exception as exc:
                self.report['phase']='terrain-unavailable';self.report['error']=str(exc)
                self.retry_at=now+2
            self.future=None
        # Bound publication work. A full ring retains the exact pending packet.
        deadline=time.monotonic()+.002;sent=0
        while self.pending and time.monotonic()<deadline and sent<262144:
            kind,payload,ready_region=self.pending[0]
            if not self.writer.write_message(kind,payload):
                self.report['phase']='waiting-for-collision-consumer';break
            self.pending.popleft();sent+=len(payload)
            if kind==COL_CLEAR:self.started=True
            if ready_region is not None:
                if kind==COL_FORGET:self.known.discard(ready_region)
                else:self.known.add(ready_region)
        self.report['published_regions']=len(self.known)
        self.report['pending_packets']=len(self.pending)
        if not self.pending and self.future is None and now>=self.retry_at:
            center=region_at(position)
            desired=set((center[0]+x,center[1]+y,center[2]+z)
                        for x,y,z in product(range(-2,3),range(-2,2),range(-2,3)))
            missing=desired-self.known
            if missing:
                if len(self.known|desired)>self.max_regions:
                    excess=len(self.known|desired)-self.max_regions
                    distant=sorted((r for r in self.known-desired if max(abs(a-b) for a,b in zip(r,center))>4),
                        key=lambda r:sum((a-b)**2 for a,b in zip(r,center)),reverse=True)
                    if len(distant)>=excess:
                        for r in distant[:excess]:
                            self.pending.append((COL_FORGET,struct.pack('<iiii',*r,self.epoch),r))
                        self.report.update(phase='evicting-distant-terrain',evicted_regions=self.report.get('evicted_regions',0)+excess)
                    else:
                        self.report.update(phase='terrain-cache-limit',error='Protected nearby collision exceeds configured terrain cache')
                else:
                    self.future=self.executor.submit(self.prepare,self.assets,tuple(position),
                                                     frozenset(self.known),self.epoch,not self.started)
                    self.report['phase']='preparing-nearby-terrain'
            else:self.report['phase']='ready'
        return dict(self.report)

    def close(self):
        self.closed=True
        if self.future:self.future.cancel()
        self.executor.shutdown(wait=False,cancel_futures=True)
