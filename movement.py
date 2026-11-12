"""Fail-closed Minecraft movement authority, independent of Windows APIs."""
import math

MC_COLLISION_READY = 1 << 8
MC_FLYING = 1 << 7


class MovementAuthority:
    def __init__(self):
        self.active = False
        self.reason = 'disabled'
        self.pending_since = None
        self.hold_position = None
        self.hold_teleport = None

    def target(self, *, enabled, now_ms, mc_heartbeat, renderer_heartbeat,
               mc, teleport, position, now):
        self.active = False
        self.reason = 'disabled'
        if not enabled:
            return None
        if not mc or not all(0 <= now_ms - beat <= 500
                            for beat in (mc_heartbeat, renderer_heartbeat)):
            self.reason = 'stale endpoint'
            return None
        flags = mc['flags']
        if not flags & 1 or flags & (2 | 32):
            self.reason = 'world unavailable, menu or death'
            return None
        if not flags & MC_COLLISION_READY:
            self.reason = 'waiting for real terrain collision'
            return None
        if mc['teleport_ack'] != teleport:
            self.reason = 'waiting for teleport acknowledgement'
            return None
        point = tuple(mc['position'])
        if len(point) != 3 or not all(math.isfinite(v) and abs(v) < 20000 for v in point):
            self.reason = 'invalid Minecraft position'
            return None
        distance = math.dist(point, position)
        # Minecraft may outpace game-thread corrections during a skipped tick. Recover only
        # within the same acquired, fresh, collision-ready session;
        # individual native commands remain capped at half a meter.
        recovery_limit=16 if self.hold_position is not None and self.hold_teleport==teleport else 2
        # A fresh initial native spawn can be inside a placed MC floor. Accept
        # only a collision-ready upward escape in the same vertical column.
        if self.hold_position is None and math.hypot(point[0]-position[0],point[2]-position[2]) <= .01 and 0 <= point[1]-position[1] <= 4:
            recovery_limit=4
        if distance > recovery_limit:
            self.reason = 'position divergence; resynchronization required'
            return None
        self.active = True
        self.reason = 'Minecraft physics'
        self.hold_position = point
        self.hold_teleport = teleport
        if distance < 0.01:
            # Refresh even a stationary target: native physics may integrate
            # between host samples. Only one bounded mailbox request is pending.
            return point
        # Bound each game-thread correction; never raise Process.nudge's limit.
        factor = min(1., 0.5 / distance)
        return tuple(a + (b - a) * factor for a, b in zip(position, point))

    def retains_session(self, *, now_ms, mc_heartbeat, mc, teleport):
        """Keep the acquired support epoch across brief input/renderer pauses."""
        if self.hold_position is None or self.hold_teleport != teleport:
            return False
        if not mc or not 0 <= now_ms-mc_heartbeat <= 1500:
            return False
        flags=mc['flags']
        return bool(flags&1 and not flags&32 and (
            mc['teleport_ack']==teleport or
            (not flags&MC_COLLISION_READY and mc['teleport_ack']==teleport-1)))

    def hold_target(self, *, now_ms, mc_heartbeat, renderer_heartbeat, mc, teleport, position):
        """Stationary support after input/menu release, never new movement."""
        if self.hold_position is None or self.hold_teleport!=teleport:return None
        if not mc or not all(0<=now_ms-beat<=500 for beat in (mc_heartbeat,renderer_heartbeat)):return None
        if not self.retains_session(now_ms=now_ms,mc_heartbeat=mc_heartbeat,mc=mc,teleport=teleport):return None
        # Recover only to our already validated stationary anchor. New walking
        # targets require fresh collision and the same acquired epoch.
        recovery_limit=16
        if not all(math.isfinite(v) for v in position) or math.dist(self.hold_position,position)>recovery_limit:return None
        distance=math.dist(self.hold_position,position)
        factor=min(1.,.5/distance) if distance else 1.
        self.active=True;self.reason='holding last validated Minecraft position'
        return tuple(a+(b-a)*factor for a,b in zip(position,self.hold_position))
