from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest,ctypes,struct
from pathlib import Path
sys.path.insert(0,str(PROJECT_ROOT))
from host_link import MouseCapture
from movement_completion import completion
class User:
 def __init__(self):self.pid=42;self.cursor=(600,600);self.keys={};self.warps=[];self.warp_ok=True;self.calls=0
 def GetForegroundWindow(self):return 123
 def GetWindowThreadProcessId(self,w,p):p._obj.value=self.pid
 def GetAsyncKeyState(self,k):self.calls+=1;return self.keys.get(k,0)
 def GetCursorPos(self,p):p._obj.x,p._obj.y=self.cursor;return 1
 def SetCursorPos(self,x,y):self.warps.append((x,y));self.cursor=(x,y) if self.warp_ok else self.cursor;return self.warp_ok
class Kernel:
 def GetTickCount64(self):return 1000
class Link:
 def __init__(self):self.memory=bytearray(4096);self.kernel=Kernel();self.flags=261
 def mc(self):return {'flags':self.flags}
 def atomic_add(self,p,d):p._obj.value+=d
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=MouseCapture.__new__(MouseCapture);self.c.user=User();self.c.link=Link();self.c.pid=42
  self.c.mouse_locked=False;self.c.mouse_center=None;self.c.cursor_failures=0;self.c.warp_failures=0
  m=self.c.link.memory
  struct.pack_into('<I',m,0xc68,1);struct.pack_into('<I',m,0xc48,1);struct.pack_into('<Q',m,0xc60,1000);struct.pack_into('<ii',m,0xcb0,500,500)
 def test_mouse_stroke_reaches_shared_delta_once(self):
  self.c.poll_physical();self.assertEqual(struct.unpack_from('<ii',self.c.link.memory,0xc54),(0,0))
  self.c.user.cursor=(508,496);self.c.poll_physical()
  self.assertEqual(struct.unpack_from('<ii',self.c.link.memory,0xc54),(8,-4))
  self.c.poll_physical();self.assertEqual(struct.unpack_from('<ii',self.c.link.memory,0xc54),(8,-4))
 def test_keyboard_samples_external_source(self):
  self.c.user.keys[ord('W')]=0x8000;self.c.poll_physical();self.assertEqual(self.c.link.memory[0xd00+ord('W')],1)
  self.c.user.keys.clear();self.c.poll_physical();self.assertEqual(self.c.link.memory[0xd00+ord('W')],0)
 def test_unattended_does_not_sample_or_warp(self):
  struct.pack_into('<I',self.c.link.memory,0xc68,0);self.c.poll_physical()
  self.assertEqual(self.c.user.calls,0);self.assertFalse(self.c.user.warps);self.assertFalse(any(self.c.link.memory[0xd00:0xe00]))
 def test_other_window_releases_input(self):
  self.c.user.pid=99;self.c.poll_physical();self.assertFalse(self.c.user.warps);self.assertEqual(self.c.user.calls,0)
 def test_menu_cursor_moves_without_warp(self):
  self.c.link.flags|=2;self.c.poll_physical();self.assertFalse(self.c.user.warps)
  self.assertEqual(struct.unpack_from('<ii',self.c.link.memory,0xccc),(600,600));self.assertEqual(struct.unpack_from('<I',self.c.link.memory,0xcc8)[0],1)
 def test_failed_warp_does_not_enable_motion(self):
  self.c.user.warp_ok=False;self.c.poll_physical();self.assertFalse(self.c.mouse_locked);self.assertEqual(self.c.warp_failures,1)
  self.c.user.cursor=(700,700);self.c.poll_physical();self.assertEqual(struct.unpack_from('<ii',self.c.link.memory,0xc54),(0,0))
 def test_stale_renderer_never_warps(self):
  struct.pack_into('<Q',self.c.link.memory,0xc60,0);self.c.poll_physical();self.assertFalse(self.c.user.warps)
 def test_claimed_command_waits_for_result(self):self.assertEqual(completion(0,0,.01,True),'pending')
 def test_published_success_finishes(self):self.assertEqual(completion(0,2,.1,True),'complete')
 def test_real_rejection_stays_rejected(self):self.assertEqual(completion(0,-1,.1,True),'rejected')
 def test_wait_remains_bounded(self):self.assertEqual(completion(0,0,.51,True),'stalled')
 def test_focus_revokes_wait(self):self.assertEqual(completion(3,0,.01,False),'released')
if __name__=='__main__':unittest.main(verbosity=2)
