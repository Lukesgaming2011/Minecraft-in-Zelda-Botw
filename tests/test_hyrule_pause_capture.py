from support import ROOT as PROJECT_ROOT, NATIVE
import ast,ctypes,struct,types,unittest
from pathlib import Path
root=Path(str(PROJECT_ROOT))
src=ast.parse((root/'host_link.py').read_text());method=next(n for c in src.body if isinstance(c,ast.ClassDef) and c.name=='MouseCapture' for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='poll_physical')
ns={'ctypes':ctypes,'struct':struct};exec(compile(ast.Module(body=[method],type_ignores=[]),'actual_capture_policy','exec'),ns)
class User:
 def __init__(self,keys=(),foreground=7):self.keys=keys;self.foreground=foreground;self.warps=0
 def GetForegroundWindow(self):return 1
 def GetWindowThreadProcessId(self,win,out):out._obj.value=self.foreground
 def GetAsyncKeyState(self,vk):return 0x8000 if vk in self.keys else 0
 def GetCursorPos(self,out):out._obj.x=100;out._obj.y=100;return 1
 def SetCursorPos(self,*p):self.warps+=1;return 1
class Policy(unittest.TestCase):
 def run_case(self,flags=1,keys=(),foreground=7,enabled=1):
  mem=bytearray(0xe00);struct.pack_into('<I',mem,0xc68,1);struct.pack_into('<I',mem,0xc48,enabled);struct.pack_into('<Q',mem,0xc60,1000);struct.pack_into('<ii',mem,0xcb0,100,100)
  link=types.SimpleNamespace(memory=mem,kernel=types.SimpleNamespace(GetTickCount64=lambda:1000),mc=lambda:{'flags':flags})
  obj=types.SimpleNamespace(user=User(keys,foreground),link=link,pid=7,mouse_locked=False,mouse_center=None,warp_failures=0,cursor_failures=0)
  ns['poll_physical'](obj);return obj,mem
 def test_gameplay_captures(self):o,m=self.run_case();self.assertEqual(o.user.warps,1);self.assertEqual(struct.unpack_from('<I',m,0xcc8)[0],3)
 def test_pause_free_cursor(self):o,m=self.run_case(flags=3);self.assertEqual(o.user.warps,0);self.assertEqual(struct.unpack_from('<I',m,0xcc8)[0],1)
 def test_alt_tab_never_warps(self):o,m=self.run_case(keys=(0xa4,9));self.assertEqual(o.user.warps,0);self.assertFalse(o.mouse_locked)
 def test_windows_key_never_warps(self):o,m=self.run_case(keys=(0x5b,));self.assertEqual(o.user.warps,0)
 def test_other_app_never_captures(self):o,m=self.run_case(foreground=8);self.assertEqual(o.user.warps,0);self.assertEqual(m[0xd00:0xe00],bytes(256))
 def test_f7_release_never_warps(self):o,m=self.run_case(enabled=0);self.assertEqual(o.user.warps,0)
if __name__=='__main__':unittest.main(verbosity=2)

