"""Bounded native camera release check; no physical mouse input."""
import math
class MouseStopProbe:
    def __init__(self):self.start=None;self.samples=[];self.finished=False;self.reported=False
    def step(self,now,direction,ready):
        if self.start is None:
            if not ready:return None
            self.start=now
        t=now-self.start
        yaw=math.degrees(math.atan2(direction[0],direction[2]))
        self.samples.append((t,yaw))
        if t>=2.3:self.finished=True
        return (.5 if t<.3 else 0.,0.)
    def report(self):
        def distance(a,b):return abs((a-b+180)%360-180)
        before=self.samples[0][1]
        release=next((y for t,y in self.samples if t>=.3),before)
        settled=next((y for t,y in self.samples if t>=.6),release)
        end=self.samples[-1][1]
        turn=distance(before,release);drift=distance(settled,end)
        return dict(passed=self.finished and turn>1 and drift<2,turn_degrees=turn,late_drift_degrees=drift,physical_mouse_capture=False,samples=self.samples)
