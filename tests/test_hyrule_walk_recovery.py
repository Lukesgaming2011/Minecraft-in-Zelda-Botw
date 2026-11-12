from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest
sys.path.insert(0,str(PROJECT_ROOT))
from movement import MovementAuthority
class WalkingRecovery(unittest.TestCase):
 def args(self):return dict(enabled=True,now_ms=1000,mc_heartbeat=990,renderer_heartbeat=990,teleport=1,position=(0,0,0),now=1,mc=dict(flags=257,teleport_ack=1,position=(0,0,0)))
 def test_acquired_walk_recovers_from_native_drop(self):
  a=MovementAuthority();d=self.args();a.target(**d);d['position']=(0,-4,0);self.assertEqual(a.target(**d),(0,-3.5,0));self.assertTrue(a.active)
 def test_unknown_initial_far_spawn_still_rejected(self):
  a=MovementAuthority();d=self.args();d['mc']['position']=(5,0,0);self.assertIsNone(a.target(**d))
 def test_new_epoch_does_not_inherit_recovery(self):
  a=MovementAuthority();d=self.args();a.target(**d);d['teleport']=2;d['mc']['teleport_ack']=2;d['mc']['position']=(5,0,0);self.assertIsNone(a.target(**d))
 def test_even_acquired_walk_has_maximum_recovery_radius(self):
  a=MovementAuthority();d=self.args();a.target(**d);d['mc']['position']=(17,0,0);self.assertIsNone(a.target(**d))
if __name__=='__main__':unittest.main(verbosity=2)
