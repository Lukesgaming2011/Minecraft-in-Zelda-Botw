from support import ROOT as PROJECT_ROOT, NATIVE
import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(PROJECT_ROOT))
from ground_validation import load_anchor,save_anchor
class CalibrationTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT/'tests'));self.addCleanup(self.t.cleanup);self.path=Path(self.t.name)/'anchor.json';self.assets=Path(self.t.name)/'assets'
  self.report=dict(position=[1,2,3],ground_match_required=True,native_height_error=.01)
 def test_verified_nearby_anchor_survives_restart(self):
  self.assertTrue(save_anchor(self.path,self.assets,self.report));self.assertEqual(load_anchor(self.path,self.assets,[4,3,5]),[1,2,3])
 def test_unverified_streaming_position_is_never_persisted(self):
  self.report['ground_match_required']=False;self.assertFalse(save_anchor(self.path,self.assets,self.report));self.assertFalse(self.path.exists())
 def test_distant_or_other_assets_rejected(self):
  save_anchor(self.path,self.assets,self.report);self.assertIsNone(load_anchor(self.path,self.assets,[100,2,3]));self.assertIsNone(load_anchor(self.path,self.assets/'other',[1,2,3]))
 def test_malformed_cache_ignored(self):
  self.path.write_text('{');self.assertIsNone(load_anchor(self.path,self.assets,[1,2,3]))
 def test_nested_verified_anchor_used(self):
  self.assertTrue(save_anchor(self.path,self.assets,dict(ground_match_required=False,ground_validation_anchor=self.report)))
if __name__=='__main__':unittest.main(verbosity=2)
