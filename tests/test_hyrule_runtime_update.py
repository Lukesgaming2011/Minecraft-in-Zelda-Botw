from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest,struct,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(str(PROJECT_ROOT))
sys.path[:0]=[str(PROJECT_ROOT),str(NATIVE)]
from bridge import Process
import launch
class FakeProcess:
 nudge=Process.nudge
 def __init__(self,current=(0,0,0),busy=False):self.current=current;self.busy=busy;self.base=0;self.writes=[]
 def position(self):return self.current
 def get(self,o):return int(self.busy) if o==0x10 else 0 if o==0x190 else 0x20000000
 def read(self,a,n):return struct.pack('>I',0x101e5ffc if a==0x200000e8 else 0x02d66abc)
 def put(self,o,v):self.writes.append((o,v))
 def set(self,o,v):self.writes.append((o,v))
class NudgeTests(unittest.TestCase):
 def test_gravity_race_rebases_half_meter(self):
  p=FakeProcess(current=(0,-3,0));self.assertTrue(p.nudge((0,.5,0),rebase=True))
  self.assertEqual(struct.unpack('>fff',p.writes[0][1]),(0,-2.5,0));self.assertEqual(p.writes[-1],(0x10,3))
 def test_default_oversized_command_still_rejected(self):
  p=FakeProcess();self.assertRaises(ValueError,p.nudge,(0,3,0));self.assertEqual(p.writes,[])
 def test_busy_mailbox_preserved(self):
  p=FakeProcess(busy=True);self.assertFalse(p.nudge((0,3,0),rebase=True));self.assertEqual(p.writes,[])
 def test_invalid_target_never_writes(self):
  p=FakeProcess();self.assertRaises(ValueError,p.nudge,(0,float('nan'),0),rebase=True);self.assertEqual(p.writes,[])
 def test_small_command_keeps_exact_target(self):
  p=FakeProcess();self.assertTrue(p.nudge((0,.25,0),rebase=True));self.assertEqual(struct.unpack('>fff',p.writes[0][1]),(0,.25,0))
 def test_caller_smaller_bound_is_respected(self):
  p=FakeProcess();p.nudge((0,3,0),max_distance=.125,rebase=True);self.assertEqual(struct.unpack('>fff',p.writes[0][1]),(0,.125,0))
class LauncherTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT/'tests'));assert Path(self.tmp.name).resolve().parent==(PROJECT_ROOT/'tests').resolve();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'project';self.lab=Path(self.tmp.name)/'lab';self.mods=Path(self.tmp.name)/'mods'
  self.addon=self.root/'dist/HyruleCraft.addon64';self.jar=self.root/'fabric/build/libs/hyrulecraft-0.1.0-botw-dev.jar'
  for p in (self.addon,self.jar,self.root/'renderer/HyruleCraft.fx',self.root.parent/'HyruleBlocks/generated/HyruleBlocks/patch_bridge.asm',self.root.parent/'HyruleBlocks/generated/HyruleBlocks/rules.txt'):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'new')
 def sync(self,mc=False,cemu=False):launch.sync_runtime_artifacts(self.root,self.lab,self.mods,minecraft_running=mc,cemu_running=cemu)
 def test_stopped_instances_receive_current_artifacts(self):
  self.sync();self.assertEqual((self.lab/self.addon.name).read_bytes(),b'new');self.assertEqual((self.mods/self.jar.name).read_bytes(),b'new')
 def test_running_owners_are_never_overwritten(self):
  self.lab.mkdir();self.mods.mkdir();(self.lab/self.addon.name).write_bytes(b'old');(self.mods/self.jar.name).write_bytes(b'old')
  self.assertRaises(RuntimeError,self.sync,True,True);self.assertEqual((self.lab/self.addon.name).read_bytes(),b'old');self.assertEqual((self.mods/self.jar.name).read_bytes(),b'old')
 def test_matching_build_allowed_while_running(self):self.sync();self.sync(True,True)
 def test_missing_build_does_not_launch_silently(self):self.jar.unlink();self.assertRaises(FileNotFoundError,self.sync)
 def test_double_launch_does_not_kill_or_restart_game(self):
  with patch.object(launch,'is_duplicate_host_running',return_value=True),patch.object(launch,'start_minecraft') as start,patch.object(launch.subprocess,'run') as run:
   self.assertEqual(launch.main([]),0);start.assert_not_called();run.assert_not_called()
if __name__=='__main__':unittest.main(verbosity=2)
