"""Minecraft-style pixel deltas to exact camera angles, without stick inertia."""
import math
class DirectMouse:
 def __init__(self,scale=.5,invert_y=False):
  from runtime_config import mouse_scale
  self.scale=mouse_scale(scale);self.invert_y=invert_y;self.yaw=self.pitch=None
 def step(self,dx,dy,sensitivity,direction):
  if self.yaw is None:
   self.yaw=-math.degrees(math.atan2(direction[0],direction[2]))
   self.pitch=-math.degrees(math.asin(max(-1.,min(1.,direction[1]))))
  if all(math.isfinite(v) for v in (dx,dy,sensitivity)):
   gain=(max(0.,min(1.,sensitivity))*.6+.2)**3*8*.15*self.scale
   self.yaw=(self.yaw+dx*gain+180)%360-180
   self.pitch=max(-89.,min(89.,self.pitch+dy*gain*(-1 if self.invert_y else 1)))
  y,p=math.radians(self.yaw),math.radians(self.pitch)
  return (-math.sin(y)*math.cos(p),-math.sin(p),math.cos(y)*math.cos(p))
class DirectMouseProbe:
 def __init__(self):self.start=None;self.sent=False;self.samples=[];self.finished=self.reported=False
 def step(self,now,direction,ready):
  if self.start is None:
   if not ready:return None
   self.start=now
  t=now-self.start;yaw=-math.degrees(math.atan2(direction[0],direction[2]))
  self.samples.append((t,yaw))
  if t>=2:self.finished=True
  if t>=.2 and not self.sent:self.sent=True;return (80,0)
  return (0,0)
 def report(self,expected_turn=6):
  delta=lambda a,b:abs((a-b+180)%360-180)
  baseline=self.samples[0][1];end=self.samples[-1][1]
  settled=next((y for t,y in self.samples if t>=.5),end)
  drift=delta(settled,end);turn=delta(baseline,end)
  return dict(passed=self.finished and abs(turn-expected_turn)<.5 and drift<.1,turn_degrees=turn,late_drift_degrees=drift,physical_mouse_capture=False,samples=self.samples)
