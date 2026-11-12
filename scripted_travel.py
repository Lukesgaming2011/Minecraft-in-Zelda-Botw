import time,math,json
from pathlib import Path
root=Path(__file__).resolve().parent
class TravelProbe:
 def __init__(self):
  self.finished=self.reported=self.passed=False;self.start=None;self.origin=None;self.samples=[];self.reason='Waiting for authority';self.stage='walking_back';self.max_error=0;self.farthest=0;self.regions=0;self.max_horizontal=0;self.boundary_since=None
 def step(self,now,mc,native,ready):
  if self.finished:return set()
  if self.start and now-self.start>55:self.finish('Trial timed out or blocked');return set()
  if not ready:return set()
  p=mc['position']; flags=mc['flags']
  if flags & (2|32|64|128):self.finish('Menu/death/swimming/flying: trial invalid');return set()
  if self.start is None:
   if math.dist(p,native)>.5:return set()
   self.start=now;self.origin=tuple(p)
  horizontal=math.hypot(p[0]-native[0],p[2]-native[2]);self.max_horizontal=max(self.max_horizontal,horizontal);
  d=math.hypot(p[0]-self.origin[0],p[2]-self.origin[2]);err=math.dist(p,native);self.max_error=max(self.max_error,err);self.farthest=max(self.farthest,d)
  try:self.regions=max(self.regions,json.loads((root/'link-status.json').read_text()).get('terrain_coverage',{}).get('published_regions',0))
  except (OSError,ValueError):pass
  self.samples.append({'t':now-self.start,'mc':p,'native':native,'gap':err,'flags':flags,'stage':self.stage})
  if horizontal>2.3:self.finish('Tracking guard exceeded horizontal limit');return set()
  if horizontal>1.8:
   if self.boundary_since is None:self.boundary_since=now
   elif now-self.boundary_since>4:self.passed=False;self.finish('Tracking guard held runaway horizontal movement for 4s');return set()
  else:self.boundary_since=None
  if err>7 or d>100 or abs(p[1]-self.origin[1])>12:self.finish('Bounded tracking/height limit exceeded');return set()
  if d>=32:self.passed=self.regions>75;self.finish('Completed bounded 32m walking trial');return set()
  return {22} if now-self.start>.8 else set()
 def finish(self,reason):self.finished=True;self.reason=reason;self.stage='complete'
 def report(self):return {'passed':self.passed,'mode':'walking','reason':self.reason,'farthest_m':self.farthest,'published_regions':self.regions,'max_tracking_error_m':self.max_error,'stable_support':self.max_error<=.5,'max_horizontal_tracking_error_m':self.max_horizontal,'physical_capture':False,'samples':self.samples}
