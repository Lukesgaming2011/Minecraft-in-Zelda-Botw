from support import ROOT
import json, math, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from runtime_config import load_config, inspect_setup, native_directory, mouse_scale
from direct_mouse import DirectMouse, DirectMouseProbe
import launch
class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.file=self.root/'local.json'
    def load(self,data):
        self.file.write_text(json.dumps(data));return load_config(self.root,self.file)
    def test_relative_paths_follow_config_file(self):
        c=self.load({'cemu_directory':'test-lab'});self.assertEqual(c['cemu_directory'],self.root/'test-lab')
    def test_defaults_keep_lower_sensitivity(self):self.assertEqual(load_config(self.root)['mouse_scale'],.5)
    def test_typo_is_rejected(self):self.assertRaises(ValueError,self.load,{'sensitivty':.3})
    def test_scale_rejects_nonfinite_and_out_of_bounds(self):
        for v in (float('nan'),float('inf'),0,3,True,None,[],{}):self.assertRaises(ValueError,mouse_scale,v)
    def test_boolean_settings_are_not_strings(self):self.assertRaises(ValueError,self.load,{'fullscreen':'false'})
    def test_instance_name_cannot_escape_or_inject_shell(self):
        for n in ('../SkyCraft','SkyCraft;cmd',"abc'",'abc*',''):
            self.assertRaises(ValueError,self.load,{'instance_name':n})
    def test_explicit_missing_config_reports_error(self):self.assertRaises(FileNotFoundError,load_config,self.root,self.file)
    def test_blank_lab_has_clear_error(self):self.assertRaisesRegex(ValueError,'cannot be blank',self.load,{'cemu_directory':''})
    def test_bad_json(self):
        self.file.write_text('{');self.assertRaises(ValueError,load_config,self.root,self.file)
    def test_incomplete_doctor_lists_all_dependencies(self):
        checks=inspect_setup(self.root,load_config(self.root));self.assertGreaterEqual(len(checks),12);self.assertTrue(any(not c['ok'] for c in checks))
    def test_doctor_never_starts_processes(self):
        self.load({'cemu_directory':'lab'})
        with patch.object(launch,'ROOT',self.root),patch.object(launch.subprocess,'Popen') as spawn,patch.object(launch,'get_kernel32') as kernel:
            self.assertEqual(launch.main(['--doctor','--config',str(self.file)]),1);spawn.assert_not_called();kernel.assert_not_called()
    def test_windowed_overrides_fullscreen_default(self):self.assertIs(launch.parse_args(['--windowed']).fullscreen,False)
    def test_conflicting_display_modes_rejected(self):
        with self.assertRaises(SystemExit):launch.parse_args(['--fullscreen','--windowed'])
    def test_invalid_cli_scale_rejected(self):
        with self.assertRaises(SystemExit):launch.parse_args(['--mouse-scale','nan'])
    def test_packaged_native_is_preferred(self):
        (self.root/'native').mkdir();(self.root/'native/bridge.py').touch();self.assertEqual(native_directory(self.root),self.root/'native')
    def test_mouse_scale_controls_real_angle(self):
        low=DirectMouse(scale=.25);high=DirectMouse(scale=1)
        low.step(80,0,.5,(0,0,1));high.step(80,0,.5,(0,0,1))
        self.assertAlmostEqual(low.yaw,3);self.assertAlmostEqual(high.yaw,12)
    def test_invert_y_changes_pitch_only(self):
        a=DirectMouse(invert_y=False);b=DirectMouse(invert_y=True)
        a.step(40,40,.5,(0,0,1));b.step(40,40,.5,(0,0,1))
        self.assertAlmostEqual(a.pitch,-b.pitch);self.assertAlmostEqual(a.yaw,b.yaw)
if __name__=='__main__':unittest.main()
