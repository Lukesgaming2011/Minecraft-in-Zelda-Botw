"""Bounded direct-Minecraft keyboard probe. Never polls or injects Windows input.

The host owns event production and applies the returned complete SDL key set.
A pass requires observed Minecraft behavior and sampled native Link tracking;
it is not evidence of working physical keyboard/mouse capture.
"""
import math


class ScriptedControls:
    WALK_KEYS = {'walk_w': 26, 'walk_a': 4, 'walk_s': 22, 'walk_d': 7}
    CORE = ('walk_w', 'walk_a', 'walk_s', 'walk_d', 'jump', 'sneak', 'sprint', 'release')
    MAX_SECONDS = 25.0
    MAX_DISTANCE = 3.0
    MAX_SAMPLE_GAP = .20
    MAX_TRACKING_ERROR = .50

    def __init__(self):
        self.finished = self.passed = self.reported = False
        self.stage = 'waiting'
        self.reason = 'Waiting for ready foreground and Minecraft collision authority'
        self.started = self.origin = self.native_origin = self.last_now = None
        self.stage_since = self.stage_origin = self.stage_yaw = None
        self.phase = 'waiting'
        self.keys = set()
        self.samples = []
        self.errors = []
        self.results = {name: {'status': 'unobserved', 'observations': 0,
                              'max_tracking_error_m': 0., 'errors': []} for name in self.CORE}
        self.sequence = list(self.CORE)
        self.index = 0
        self.release_until = None
        self.jump_airborne = False
        self.jump_peak = None
        self.flag_observed = False
        self.clear_since = None
        self.max_tracking_error = 0.

    @staticmethod
    def _point(value):
        try:
            point = tuple(float(v) for v in value)
        except (TypeError, ValueError, OverflowError):
            return None
        return point if len(point) == 3 and all(math.isfinite(v) and abs(v) < 20000 for v in point) else None

    def _abort(self, reason):
        if self.stage in self.results and self.results[self.stage]['status'] == 'running':
            self._complete(False, reason)
        self.errors.append({'stage': self.stage, 'kind': 'abort', 'reason': reason})
        self.finished = True
        self.passed = False
        self.reason = reason
        self.keys.clear()
        return set()

    def _enter(self, now, point, yaw, flags):
        self.stage = self.sequence[self.index]
        self.stage_since, self.stage_origin, self.stage_yaw = now, point, yaw
        self.phase = 'action'
        self.results[self.stage]['status'] = 'running'
        self.results[self.stage]['start_flags'] = flags
        self.flag_observed = False
        self.jump_airborne = False
        self.jump_peak = point[1]
        self.clear_since = None
        self.reason = 'Observing ' + self.stage

    def _complete(self, passed, error=None, **evidence):
        result = self.results[self.stage]
        result.update(evidence)
        result['status'] = 'passed' if passed else 'failed'
        if error:
            result['errors'].append(error)
            self.errors.append({'stage': self.stage, 'kind': 'action', 'reason': error})

    def _advance(self, now, pause=.40):
        self.keys.clear()
        self.index += 1
        self.phase = 'release_between'
        self.release_until = now + pause

    def _walk_evidence(self, point):
        yaw = math.radians(self.stage_yaw)
        forward = (-math.sin(yaw), math.cos(yaw))
        left = (math.cos(yaw), math.sin(yaw))
        if self.stage == 'walk_s': axis = tuple(-v for v in forward)
        elif self.stage == 'walk_a': axis = left
        elif self.stage == 'walk_d': axis = tuple(-v for v in left)
        else: axis = forward
        delta = (point[0] - self.stage_origin[0], point[2] - self.stage_origin[2])
        projected = sum(a*b for a, b in zip(delta, axis))
        horizontal = math.hypot(*delta)
        return {'displacement_m': horizontal, 'expected_axis_displacement_m': projected,
                'start_yaw_degrees': self.stage_yaw, 'start_position': list(self.stage_origin),
                'end_position': list(point)}

    def step(self, now, mc, native_position, ready):
        if self.finished:
            return set()
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            return self._abort('Nonfinite observation clock')
        if not ready:
            if self.started is not None:
                return self._abort('Foreground, endpoint health or collision authority lost')
            return set()
        point = self._point(mc.get('position')) if isinstance(mc, dict) else None
        native = self._point(native_position)
        if point is None or native is None:
            return self._abort('Missing or nonfinite Minecraft/native position')
        flags = mc.get('flags')
        if not isinstance(flags, int) or not flags & 1 or not flags & 256 or flags & (2 | 32 | 64 | 128):
            return self._abort('World/collision health unavailable, menu, death, swimming or Creative flying')
        yaw = mc.get('yaw')
        if not isinstance(yaw, (int, float)) or not math.isfinite(yaw):
            return self._abort('Missing or nonfinite gameplay yaw')
        if 'health' in mc and (not isinstance(mc['health'], (int, float)) or
                               not math.isfinite(mc['health']) or mc['health'] <= 0):
            return self._abort('Minecraft health is invalid or depleted')
        if self.started is None:
            if not flags & 4:
                self.reason = 'Waiting for initial grounded support'
                return set()
            self.started = self.last_now = self.stage_since = now
            self.origin, self.native_origin = point, native
            self.stage, self.phase = 'settle', 'settle'
        else:
            if now < self.last_now or now - self.last_now > self.MAX_SAMPLE_GAP:
                return self._abort('Observation clock reversed or gap exceeds 200ms')
            self.last_now = now
        if now - self.started > self.MAX_SECONDS:
            return self._abort('Probe exceeded 25s bound')
        if math.dist(point, self.origin) > self.MAX_DISTANCE or math.dist(native, self.native_origin) > self.MAX_DISTANCE:
            return self._abort('Minecraft or Link exceeded 3m origin bound')
        error = math.dist(point, native)
        self.max_tracking_error = max(self.max_tracking_error, error)
        self.samples.append({'t': round(now-self.started, 5), 'stage': self.stage,
                             'phase': self.phase, 'mc': list(point), 'link': list(native),
                             'flags': flags, 'keys_previously_requested': sorted(self.keys),
                             'tracking_error_m': error})
        if self.stage in self.results:
            result = self.results[self.stage]
            result['max_tracking_error_m'] = max(result['max_tracking_error_m'], error)
            if self.phase == 'action': result['observations'] += 1
        if error > self.MAX_TRACKING_ERROR:
            return self._abort('Sampled native Link tracking error exceeded 0.50m')
        if len(self.samples) > 5000:
            return self._abort('Observation count exceeded bounded report capacity')
        if self.phase == 'settle':
            if now - self.stage_since >= .50:
                self._enter(now, point, yaw, flags)
            else:
                return set()
        elif self.phase == 'release_between':
            if now < self.release_until:
                return set()
            if self.index >= len(self.sequence):
                self.finished = True
                self.passed = all(result['status'] == 'passed' for result in self.results.values())
                self.stage = 'complete'
                self.reason = ('All core scripted behaviors observed with sampled native tracking; physical controls unverified'
                               if self.passed else 'One or more core scripted behaviors failed or remained unobserved')
                return set()
            self._enter(now, point, yaw, flags)
        elapsed = now - self.stage_since
        result = self.results[self.stage]
        if self.stage in self.WALK_KEYS:
            if elapsed < .25:
                self.keys = {self.WALK_KEYS[self.stage]}
            else:
                evidence = self._walk_evidence(point)
                observed = result['observations'] >= 4 and evidence['expected_axis_displacement_m'] >= .04
                self._complete(observed, None if observed else 'Requested walk had insufficient samples or displacement in expected direction', **evidence)
                self._advance(now)
        elif self.stage == 'jump':
            if not result['start_flags'] & 4:
                self._complete(False, 'Jump stage did not start grounded; no Space emitted')
                self._advance(now)
                return set()
            # Exactly one Space press, released after150ms: never a Creative double tap.
            self.keys = {44} if elapsed < .15 else set()
            self.jump_peak = max(self.jump_peak, point[1])
            if not flags & 4 and point[1] > self.stage_origin[1] + .10:
                self.jump_airborne = True
            landed = self.jump_airborne and bool(flags & 4) and elapsed > .20
            if landed or elapsed >= 3.0:
                observed = landed and result['observations'] >= 4
                self._complete(observed, None if observed else 'Jump did not demonstrate airborne height followed by grounded landing',
                               airborne_observed=self.jump_airborne, grounded_landing_observed=landed,
                               peak_y=self.jump_peak, start_y=self.stage_origin[1])
                self._advance(now)
        elif self.stage == 'sneak':
            self.flag_observed = self.flag_observed or bool(flags & 8)
            if elapsed < .35:
                self.keys = {225}
            else:
                observed = self.flag_observed and not result['start_flags'] & 8 and result['observations'] >= 4
                self._complete(observed, None if observed else 'Sneak flag8 not observed under requested left Shift', flag8_observed=self.flag_observed)
                self._advance(now)
        elif self.stage == 'sprint':
            self.flag_observed = self.flag_observed or bool(flags & 16)
            if elapsed < .35:
                self.keys = {224, 26}
            else:
                evidence = self._walk_evidence(point)
                observed = self.flag_observed and not result['start_flags'] & 16 and result['observations'] >= 4 and evidence['expected_axis_displacement_m'] >= .04
                self._complete(observed, None if observed else 'Sprint flag16 or forward displacement not observed; nearby obstacles may block it',
                               flag16_observed=self.flag_observed, **evidence)
                self._advance(now, pause=.60)
        elif self.stage == 'release':
            self.keys.clear()
            if not flags & (8 | 16) and flags & 4:
                if self.clear_since is None: self.clear_since = now
            else:
                self.clear_since = None
            if elapsed >= .50:
                evidence = self._walk_evidence(point)
                observed = (self.clear_since is not None and now-self.clear_since >= .15 and
                            result['observations'] >= 4 and evidence['displacement_m'] <= .06)
                self._complete(observed, None if observed else 'Released controls did not settle grounded without sneak/sprint or residual movement',
                               flags8_and16_clear=not bool(flags & (8 | 16)), grounded=bool(flags & 4), **evidence)
                self._advance(now, pause=0.)
        return set(self.keys)

    def report(self):
        return {'validation_version': 1, 'kind': 'bounded direct-Minecraft core keyboard and sampled native tracking probe',
                'finished': self.finished, 'passed': self.passed, 'reason': self.reason,
                'stage': self.stage, 'max_duration_s': self.MAX_SECONDS, 'max_origin_distance_m': self.MAX_DISTANCE,
                'max_sample_gap_s': self.MAX_SAMPLE_GAP, 'tracking_error_limit_m': self.MAX_TRACKING_ERROR,
                'max_observed_tracking_error_m': self.max_tracking_error,
                'minecraft_origin': None if self.origin is None else list(self.origin),
                'native_origin': None if self.native_origin is None else list(self.native_origin),
                'stages': self.results, 'errors': self.errors, 'samples': self.samples, 'physical_input_tested': False,
                'physical_mouse_capture': False, 'all_minecraft_features_verified': False}


