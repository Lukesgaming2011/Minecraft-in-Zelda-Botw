from support import ROOT as PROJECT_ROOT, NATIVE
import ast,unittest,sys,time,struct
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(str(PROJECT_ROOT))
sys.path.insert(0,str(ROOT))
from movement_completion import completion
from mouse_look import MouseLook
from direct_mouse import DirectMouse
src=ast.parse((ROOT/'host_link.py').read_text())
def block(condition):
 node=next(n for n in ast.walk(src) if isinstance(n,ast.If) and ast.unparse(n.test)==condition)
 return compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual-host-block','exec')
MOVE=block('pending_move_since is not None')
MOUSE=block("input_enabled and mc and (not mc['flags'] & 2)")
class HostRegression(unittest.TestCase):
 def state(self,cmd=3,result=0,active=True):
  p=Mock();p.get.side_effect=lambda off,*a:cmd if off==0x10 else result
  return dict(process=p,pending_move_since=time.monotonic()-1,completion=completion,time=time,authority=Mock(active=active),movement_error=None,movement_stalls=0,movement_retry_until=0)
 def test_stall_clears_mailbox_and_retries_without_permanent_failure(self):
  d=self.state();exec(MOVE,d);self.assertIsNone(d['movement_error']);self.assertIsNone(d['pending_move_since']);self.assertEqual(d['movement_stalls'],1);self.assertGreater(d['movement_retry_until'],time.monotonic());d['process'].set.assert_called_once_with(0x10,0)
 def test_signature_rejection_remains_fatal(self):
  d=self.state(cmd=0,result=-1);exec(MOVE,d);self.assertEqual(d['movement_error'],'Player hook rejected correction')
 def test_late_completed_command_is_accepted(self):
  d=self.state(cmd=0,result=2);exec(MOVE,d);self.assertIsNone(d['pending_move_since']);self.assertEqual(d['movement_stalls'],0)
 def test_released_authority_does_not_count_as_stall(self):
  d=self.state(active=False);exec(MOVE,d);self.assertEqual(d['movement_stalls'],0);self.assertIsNone(d['movement_error'])
 def mouse(self,dx,dy=0,flags=1):
  p=Mock();d=dict(process=p,input_enabled=True,mc={'flags':flags,'sensitivity':.5},mouse_look=MouseLook(),direct_mouse=DirectMouse(),gameplay_direction=(0,0,1),dx=dx,dy=dy,math=__import__('math'),struct=struct,placement_stick=(0,0),movement_aim_x=0,authority=Mock(active=True));exec(MOUSE,d);return p
 def test_neutral_frame_is_explicitly_leased(self):
  p=self.mouse(0);p.put.assert_called_once_with(0x48,struct.pack('>ffff',0,0,0,0));p.set.assert_any_call(0x198,1)
 def test_turn_then_release_has_no_queued_turn(self):
  self.mouse(1000);p=self.mouse(0);self.assertEqual(struct.unpack('>ffff',p.put.call_args.args[1]),(0,0,0,0))
 def test_inventory_releases_native_stick(self):
  p=self.mouse(1000,flags=3);p.put.assert_not_called();p.set.assert_called_once_with(0x198,0)
if __name__=='__main__':unittest.main(verbosity=2)
