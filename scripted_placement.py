"""One bounded native camera aim and real Minecraft right click, with no OS capture."""
import math
class ScriptedPlacement:
    def __init__(self,turn_degrees=35):
        self.started=None;self.stage='waiting';self.stage_since=None;self.finished=False;self.reason='Waiting for ready foreground';self.samples=[];self.yaw_start=None;self.turn_degrees=turn_degrees
    def step(self,now,mc,ready):
        events=[];stick=(0.,0.)
        if self.finished:return stick,events
        if not ready:
            if self.started is not None:self.abort('Foreground or collision readiness lost');events=[(6,0,0,0,0)]
            return stick,events
        if self.started is None:self.started=now;self.stage='settle';self.stage_since=now
        if now-self.started>10:self.abort('Placement action exceeded 10s bound');return (0.,0.),[(6,0,0,0,0)]
        pitch=mc['pitch']
        if not math.isfinite(pitch) or pitch>60:self.abort('Camera pitch outside aim bound');return (0.,0.),[(6,0,0,0,0)]
        self.samples.append({'t':round(now-self.started,4),'pitch':pitch,'yaw':mc.get('yaw',0),'position':mc['position'],'stage':self.stage})
        elapsed=now-self.stage_since
        if self.stage=='settle' and elapsed>=2:self.stage='turn';self.stage_since=now;self.yaw_start=mc.get('yaw',0)
        elif self.stage=='turn':
            delta=abs((mc.get('yaw',0)-self.yaw_start+180)%360-180)
            if delta>=self.turn_degrees:self.stage='aim';self.stage_since=now
            elif elapsed>2:self.abort('Native camera did not complete bounded yaw turn')
            else:stick=(.8,0.)
        elif self.stage=='aim':
            if pitch<35:
                if elapsed>3:self.abort('Native camera did not reach target pitch')
                else:stick=(0.,-.8)
            else:self.stage='select';self.stage_since=now;events=[(1,34,1,0,0),(1,34,0,0,0)]
        elif self.stage=='select' and elapsed>=.6:self.stage='click';self.stage_since=now;events=[(2,3,1,0,0)]
        elif self.stage=='click' and elapsed>=.12:self.stage='verify';self.stage_since=now;events=[(2,3,0,0,0)]
        elif self.stage=='verify' and elapsed>=2:
            self.finished=True;self.reason='Input sequence complete; terrain hit, server result and visual placement require separate verification'
        return stick,events
    def abort(self,reason):self.finished=True;self.reason=reason
    def report(self):return {'kind':'bounded ground placement input probe','finished':self.finished,'reason':self.reason,'samples':self.samples,'physical_mouse_capture':False,'placement_verified':False}

