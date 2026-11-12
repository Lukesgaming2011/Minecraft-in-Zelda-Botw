from support import ROOT as PROJECT_ROOT, NATIVE
import sys,math,unittest
sys.path.insert(0,str(PROJECT_ROOT))
from direct_mouse import DirectMouse
class DirectMouseTests(unittest.TestCase):
 def test_single_stroke_and_release_endpoint(self):
  m=DirectMouse();v=m.step(80,0,.5,(0,0,1));self.assertAlmostEqual(m.yaw,6)
  for _ in range(120):self.assertEqual(m.step(0,0,.5,(1,0,0)),v)
 def test_reversal_returns_to_original(self):
  m=DirectMouse();m.step(800,0,.5,(0,0,1));v=m.step(-800,0,.5,(0,0,1));self.assertAlmostEqual(v[0],0);self.assertAlmostEqual(v[2],1)
 def test_pitch_bounded_and_vector_normalized(self):
  m=DirectMouse();v=m.step(10000,10000,1,(0,0,1));self.assertEqual(m.pitch,89);self.assertAlmostEqual(sum(x*x for x in v),1)
 def test_bad_delta_never_poison_angles(self):
  m=DirectMouse();v=m.step(0,0,.5,(0,0,1));self.assertEqual(m.step(float('nan'),0,.5,(0,0,1)),v)
 def test_initial_native_direction_preserved(self):
  v=(.6,0,.8);m=DirectMouse();out=m.step(0,0,.5,v)
  for a,b in zip(out,v):self.assertAlmostEqual(a,b)
if __name__=='__main__':unittest.main(verbosity=2)

