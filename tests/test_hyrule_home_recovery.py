from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest,struct
sys.path.insert(0,str(NATIVE))
from bridge import Process
class Fake:
 recover_home=Process.recover_home
 def __init__(self,busy=False,table=0x101e5ffc):self.busy=busy;self.table=table;self.writes=[];self.base=0
 def position(self):return (0,0,0)
 def get(self,o):return int(self.busy) if o==0x10 else 0 if o==0x190 else 0x20000000
 def read(self,a,n):return struct.pack('>I',self.table if a==0x200000e8 else 0x02d66abc)
 def set(self,o,v):self.writes.append((o,v))
 def put(self,o,v):self.writes.append((o,v))
class RecoveryTests(unittest.TestCase):
 def test_nearby_recovery_releases_support_before_warp(self):
  p=Fake();self.assertTrue(p.recover_home((20,1,0)));self.assertEqual(p.writes[0],(0x40,0));self.assertEqual(p.writes[-1],(0x10,4))
 def test_busy_never_cancels_other_commands(self):
  p=Fake(busy=True);self.assertFalse(p.recover_home((1,0,0)));self.assertFalse(p.writes)
 def test_invalid_or_distant_never_writes(self):
  for target in ((float('nan'),0,0),(97,0,0)):
   p=Fake();self.assertRaises(ValueError,p.recover_home,target);self.assertFalse(p.writes)
 def test_wrong_actor_vtable_refuses_warp(self):
  p=Fake(table=0x101e5ffd);self.assertRaises(ValueError,p.recover_home,(1,0,0));self.assertFalse(p.writes)
if __name__=='__main__':unittest.main(verbosity=2)
