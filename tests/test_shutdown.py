from support import ROOT
import ast,types,unittest
source=ast.parse((ROOT/'host_link.py').read_text())
main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
handler=next(h for node in main.body if isinstance(node,ast.Try) for h in node.handlers if isinstance(h.type,ast.Name) and h.type.id=='OSError')
class Shutdown(unittest.TestCase):
    def run_handler(self,wait):
        node=ast.Try(body=ast.parse("raise OSError('read failed')").body,handlers=[handler],orelse=[],finalbody=[])
        module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
        process=types.SimpleNamespace(handle=123,k=types.SimpleNamespace(WaitForSingleObject=lambda h,t:wait))
        exec(compile(module,'real_shutdown_handler','exec'),{'process':process,'print':lambda *a,**k:None})
    def test_closed_process_is_clean(self):self.run_handler(0)
    def test_live_process_read_failure_is_not_hidden(self):self.assertRaises(OSError,self.run_handler,258)
    def test_query_failure_is_not_hidden(self):self.assertRaises(OSError,self.run_handler,0xffffffff)
