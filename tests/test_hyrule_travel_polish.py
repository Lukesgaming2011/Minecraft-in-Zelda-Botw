from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest,struct
from pathlib import Path
from concurrent.futures import Future
sys.path.insert(0,str(PROJECT_ROOT))
from travel_prefetch import position_for_terrain
from dynamic_terrain import DynamicTerrain
from collaboration.terrain_export import COL_FORGET
class Prefetch(unittest.TestCase):
 def args(self):return dict(native=(0,0,0),mc=dict(flags=257,teleport_ack=1,position=(3,0,0)),now_ms=1000,heartbeat=990,teleport=1,anchor=(2,0,0),anchor_epoch=1)
 def test_walking_follows_minecraft_not_lagging_link(self):self.assertEqual(position_for_terrain(**self.args()),(3,0,0))
 def test_frontier_hold_can_request_missing_terrain(self):
  d=self.args();d['mc']['flags']=1;d['mc']['teleport_ack']=0;self.assertEqual(position_for_terrain(**d),(3,0,0))
 def test_stale_and_wrong_epoch_are_not_followed(self):
  for field,val in [('heartbeat',0),('anchor_epoch',2),('anchor',None)]:
   d=self.args();d[field]=val;self.assertEqual(position_for_terrain(**d),(0,0,0))
 def test_death_and_remote_positions_are_not_followed(self):
  d=self.args();d['mc']['flags']=289;self.assertEqual(position_for_terrain(**d),(0,0,0));d=self.args();d['mc']['position']=(100,0,0);self.assertEqual(position_for_terrain(**d),(0,0,0))
class Executor:
 def __init__(self):self.jobs=[]
 def submit(self,*args):f=Future();self.jobs.append((f,args));return f
 def shutdown(self,**kw):pass
class Writer:
 def __init__(self):self.accept=True;self.messages=[]
 def write_message(self,*args):
  if not self.accept:return False
  self.messages.append(args);return True
class Eviction(unittest.TestCase):
 def test_distant_collision_is_retired_then_reloaded_without_clear(self):
  w=Writer();e=Executor();d=DynamicTerrain('assets',w,executor=e,max_regions=100);d.started=True;d.known={(100,0,0)}
  d.tick((0,0,0),0);self.assertEqual(d.report['phase'],'evicting-distant-terrain');self.assertIn((100,0,0),d.known)
  d.tick((0,0,0),1);self.assertNotIn((100,0,0),d.known);self.assertEqual(w.messages,[(COL_FORGET,struct.pack('<iiii',100,0,0,1))]);self.assertEqual(len(e.jobs),1)
 def test_ring_backpressure_never_loses_eviction(self):
  w=Writer();e=Executor();d=DynamicTerrain('assets',w,executor=e,max_regions=100);d.known={(100,0,0)};d.tick((0,0,0),0);w.accept=False;d.tick((0,0,0),1);self.assertIn((100,0,0),d.known);self.assertEqual(len(d.pending),1);self.assertFalse(e.jobs)
 def test_nearby_regions_are_protected(self):
  w=Writer();d=DynamicTerrain('assets',w,executor=Executor(),max_regions=75);d.known={(3,0,0)};self.assertEqual(d.tick((0,0,0),0)['phase'],'terrain-cache-limit');self.assertFalse(d.pending)
if __name__=='__main__':unittest.main(verbosity=2)

