"""Current-frame mouse-to-stick mapping with no queued turn after release.
Native BOTW response caps large strokes; excess pixels never become momentum.
"""
import math
class MouseLook:
    def __init__(self):self.reset()
    def reset(self):self.x=self.y=0.
    def step(self,dx,dy,sensitivity=.5):
        self.reset()
        if not all(math.isfinite(v) for v in (dx,dy,sensitivity)):
            return (0.,0.)
        gain=(max(0.,min(1.,sensitivity))*.6+.2)**3*8
        return (max(-1.,min(1.,dx*gain/25.)),
                max(-1.,min(1.,-dy*gain/25.)))
