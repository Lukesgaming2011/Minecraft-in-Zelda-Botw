from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest
sys.path.insert(0,str(PROJECT_ROOT))
from movement import MovementAuthority,MC_COLLISION_READY
class HoldTests(unittest.TestCase):
 def setUp(self):
  self.a=MovementAuthority();self.mc={'flags':1|MC_COLLISION_READY|128,'teleport_ack':4,'position':(0,14,0)}
  self.kw=dict(now_ms=1000,mc_heartbeat=990,renderer_heartbeat=990,mc=self.mc,teleport=4,position=(0,14,0))
 def acquire(self):self.a.target(enabled=True,now=1,**self.kw)
 def test_unowned_session_does_not_hold(self):self.assertIsNone(self.a.hold_target(**self.kw))
 def test_releasing_input_keeps_hover_anchor(self):
  self.acquire();self.a.target(enabled=False,now=1,**self.kw)
  self.assertEqual(self.a.hold_target(**self.kw),(0,14,0))
 def test_menu_cannot_move_anchor(self):
  self.acquire();self.mc['flags']|=2;self.mc['position']=(100,100,100)
  self.assertEqual(self.a.hold_target(**self.kw),(0,14,0))
 def test_unknown_frontier_holds_previous_known_position(self):
  self.acquire();self.mc['flags']&=~MC_COLLISION_READY;self.mc['position']=(0,15,0)
  self.assertEqual(self.a.hold_target(**self.kw),(0,14,0))
 def test_death_and_stale_endpoint_release(self):
  self.acquire();self.mc['flags']|=32;self.assertIsNone(self.a.hold_target(**self.kw))
  self.mc['flags']&=~32;self.assertIsNone(self.a.hold_target(**dict(self.kw,mc_heartbeat=0)))
 def test_other_teleport_releases(self):
  self.acquire();self.assertIsNone(self.a.hold_target(**dict(self.kw,teleport=5)))
 def test_correction_remains_bounded(self):
  self.acquire();self.assertEqual(self.a.hold_target(**dict(self.kw,position=(0,13,0))),(0,13.5,0))
  self.assertEqual(self.a.hold_target(**dict(self.kw,position=(0,10,0))),(0,10.5,0))
  self.assertIsNone(self.a.hold_target(**dict(self.kw,position=(0,-3,0))))
if __name__=='__main__':unittest.main(verbosity=2)

