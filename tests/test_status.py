from support import ROOT
import json,tempfile,time,unittest
from pathlib import Path
from status import summarize
class Health(unittest.TestCase):
    def test_absent_is_not_live(self):self.assertFalse(summarize(ROOT/'not-a-status-file.json')['live'])
    def test_old_live_report_is_not_current_proof(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'state.json';p.write_text(json.dumps({'phase':'live-minecraft-renderer'}))
            self.assertTrue(summarize(p)['live']);self.assertFalse(summarize(p,now=time.time()+30)['live'])
    def test_stopped_state_is_not_live(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'state.json';p.write_text(json.dumps({'phase':'stopped'}));self.assertFalse(summarize(p)['live'])

    def test_malformed_report_is_not_live(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'state.json';p.write_text('[]');self.assertFalse(summarize(p)['live'])
