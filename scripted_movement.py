"""Bounded development probe; events go to MC, never to Windows."""
import math

class ScriptedMovement:
    def __init__(self,block,support_seconds=2,jump_on_target=False):
        self.jump_on_target=jump_on_target;self.support_jump_started=None;self.support_jump_airborne=False;self.support_jump_peak=None;self.support_seconds=support_seconds;self.block=tuple(block);self.origin=None;self.started=None;self.stage='waiting';self.reason='waiting for ready foreground';self.keys=set();self.samples=[];self.finished=False;self.on_block_since=None;self.passed=False;self.reported=False;self.jump_since=None;self.support_samples=[];self.landing_samples=[]
    def step(self,now,mc,position,ready,camera_eye=None):
        wanted=set()
        if self.finished:return wanted
        if self.started is None:
            if not ready:return wanted
            self.started=now;self.origin=tuple(position);self.stage='approach'
            if math.dist((self.block[0]+.5,self.block[2]+.5),(position[0],position[2]))>4.5:
                self.abort('Fixture is outside bounded reach');return wanted
        if not ready:self.abort('Foreground, endpoint or collision readiness lost');return wanted
        if now-self.started>8 or math.dist(position,self.origin)>6 or math.dist(mc['position'],self.origin)>6:
            self.abort('Probe duration or distance bound reached');return wanted
        if mc['flags']&128:self.abort('Creative flying invalidates walking probe');return wanted
        p=mc['position'];bx,by,bz=self.block
        supported=(bx<=p[0]<=bx+1 and bz<=p[2]<=bz+1 and abs(p[1]-(by+1))<.08 and bool(mc['flags']&4))
        self.samples.append({'t':round(now-self.started,4),'stage':self.stage,'mc':list(p),'link':list(position),'flags':mc['flags'],'supported':supported,'camera_eye':None if camera_eye is None else list(camera_eye)})
        if self.stage=='jump':
            wanted.add(225)
            if now-self.support_jump_started<.15:wanted.add(44)
            if not bool(mc['flags']&4) and p[1]>by+1.1:self.support_jump_airborne=True
            self.support_jump_peak=max(self.support_jump_peak,p[1])
            if supported and self.support_jump_airborne and now-self.support_jump_started>.2:
                self.stage='stand';self.on_block_since=now;self.support_samples=[]
            else:
                if now-self.support_jump_started>2:self.abort('Target jump did not return to grounded block support')
                return wanted
        if supported:
            self.stage='stand'
            wanted.add(225) # Hold sneak while forward momentum settles at the block edge.
            if self.on_block_since is None:self.on_block_since=now
            error=math.dist(position,p)
            height_error=abs(position[1]-(by+1))
            # Allow bounded landing convergence; report it separately, never hide it.
            if now-self.on_block_since<.3:
                self.landing_samples.append({'t':now,'error':error,'height_error':height_error})
                return wanted
            if self.jump_on_target and self.support_jump_started is None:
                self.stage='jump';self.support_jump_started=now;self.support_jump_peak=p[1]
                wanted.add(44);return wanted
            previous=self.support_samples[-1]['t'] if self.support_samples else None
            self.support_samples.append({'t':now,'error':error,'height_error':height_error})
            # Every observed supported frame counts, after the 300ms landing phase. A later
            # correction must never erase a dip or a long observation gap.
            if not all(math.isfinite(v) for v in (*position,*p)) or error>.10 or height_error>.08:
                self.abort('Native Link left support tolerance during standing');return wanted
            if previous is not None and now-previous>.15:
                self.abort('Standing observation gap exceeds 150ms');return wanted
            if now-self.support_samples[0]['t']>=self.support_seconds and len(self.support_samples)>=30:
                self.passed=True;self.finished=True
                self.reason=f'Sustained sampled support verified for {self.support_seconds:g}s; render-frame stability still requires capture'
            return wanted
        if self.stage=='stand':self.abort('Lost block support while standing');return wanted
        if now-self.started<.5:return wanted
        distance=math.dist((p[0],p[2]),(bx+.5,bz+.5))
        wanted.add(26) # SDL W
        if distance<1.3:
            wanted.add(225) # Slow approach and prevent walking off the block.
            if p[1]<by+.9 and now-self.started>1 and self.jump_since is None:self.jump_since=now
            if self.jump_since is not None and now-self.jump_since<.15:wanted.add(44)
        return wanted
    def abort(self,reason):
        self.finished=True;self.passed=False;self.reason=reason
    def report(self):
        return {'validation_version':4,'jump_on_target_requested':self.jump_on_target,'jump_airborne_verified':self.support_jump_airborne,'jump_peak_y':self.support_jump_peak,'landing_settle_s':.3,'landing_samples':self.landing_samples,'support_duration_required_s':self.support_seconds,'max_sample_gap_s':.15,'max_height_error_m':.08,'max_position_error_m':.10,'supported_samples':len(self.support_samples),'fixture':self.block,'passed':self.passed,'reason':self.reason,'samples':self.samples,'physical_mouse_capture':False,'kind':'scripted MC input and native Link tracking; not human controls validation'}

