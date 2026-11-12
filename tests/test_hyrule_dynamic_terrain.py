from support import ROOT as PROJECT_ROOT, NATIVE
import sys,unittest,time
from pathlib import Path
from concurrent.futures import Future
sys.path.insert(0,str(Path(str(PROJECT_ROOT))))
from dynamic_terrain import DynamicTerrain,prepare_batch,region_at
from collaboration.terrain_export import COL_CLEAR,COL_TRIS,COL_REGION
class Executor:
 def __init__(self):self.jobs=[]
 def submit(self,fn,*args):
  f=Future();self.jobs.append((f,fn,args));return f
 def shutdown(self,**kw):pass
class Writer:
 def __init__(self):self.accept=True;self.messages=[]
 def write_message(self,k,p):
  if not self.accept:return False
  self.messages.append((k,p));return True
class Tests(unittest.TestCase):
 def setUp(self):
  self.e=Executor();self.w=Writer();self.d=DynamicTerrain('assets',self.w,executor=self.e)
 def test_async_job_does_not_block_tick(self):
  self.d.tick((0,0,0),0);self.assertEqual(len(self.e.jobs),1)
  self.d.tick((0,0,0),1);self.assertEqual(len(self.e.jobs),1);self.assertEqual(self.w.messages,[])
 def test_backpressure_retries_same_packet_without_duplicate_clear(self):
  self.d.tick((0,0,0),0)
  self.e.jobs[0][0].set_result(([(COL_CLEAR,b'clear',None),(COL_TRIS,b'tri',None),(COL_REGION,b'reg',(0,0,0))],{}))
  self.w.accept=False;self.d.tick((0,0,0),1);self.assertFalse(self.d.started);self.assertEqual(len(self.d.pending),3)
  self.w.accept=True;self.d.tick((0,0,0),2)
  self.assertEqual(self.w.messages,[(COL_CLEAR,b'clear'),(COL_TRIS,b'tri'),(COL_REGION,b'reg')]);self.assertIn((0,0,0),self.d.known)
  self.assertFalse(self.e.jobs[-1][2][-1]);self.assertIn((0,0,0),self.e.jobs[-1][2][2])
 def test_errors_hold_terrain_and_retry_not_crash(self):
  self.d.tick((0,0,0),0);self.e.jobs[0][0].set_exception(ValueError('missing asset'))
  self.assertEqual(self.d.tick((0,0,0),1)['phase'],'terrain-unavailable')
  self.d.tick((0,0,0),2);self.assertEqual(len(self.e.jobs),1)
  self.d.tick((0,0,0),3);self.assertEqual(len(self.e.jobs),2)
 def test_known_region_not_ready_until_region_packet(self):
  self.d.tick((0,0,0),0);self.e.jobs[0][0].set_result(([(COL_TRIS,b'tri',None)],{}))
  self.d.tick((0,0,0),1);self.assertFalse(self.d.known)
 def test_cache_limit_is_bounded(self):
  self.d.max_regions=1;self.assertEqual(self.d.tick((0,0,0),0)['phase'],'terrain-cache-limit');self.assertEqual(len(self.e.jobs),0)
 def test_invalid_position(self):
  with self.assertRaises(ValueError):region_at((float('nan'),0,0))
 def test_close_stops_submission(self):
  self.d.close();self.d.tick((0,0,0),0);self.assertEqual(len(self.e.jobs),0)
 def test_authentic_travel_beyond_old_24m_crop(self):
  assets=__import__('runtime_config').load_config(PROJECT_ROOT)['terrain_directory']
  if not assets.is_dir():self.skipTest('Authentic BOTW terrain assets are local-only')
  pos=(-1031.9019775390625,251.563232421875,1806.346923828125)
  packets,report=prepare_batch(assets,pos,frozenset(),1,True)
  known={r for _,_,r in packets if r is not None};self.assertEqual(len(known),100)
  # At y=248.007 a downward tick of .08 makes the 8m swept check
  # reach region29, although the feet are still in region31. Old +/-1
  # publication never loaded29 and could permanently block movement.
  cx,cy,cz=region_at(pos)
  import math
  swept_bottom=math.floor((248.007-.08-8)/8)
  self.assertEqual(swept_bottom,cy-2)
  self.assertIn((cx,swept_bottom,cz),known)
  # +24m exceeds original footprint. Airborne feet must not reject authentic
  # terrain after initial ground transform validation.
  later=(pos[0]+24,pos[1]+3,pos[2])
  more,report2=prepare_batch(assets,later,known,1,False)
  self.assertTrue(more);self.assertFalse(any(k==COL_CLEAR for k,_,_ in more))
  self.assertTrue(all(r not in known for _,_,r in more if r is not None))
  self.assertEqual(report2['ground_match_required'],False)
  print('AUTHENTIC_TRAVEL',report['footprint'],report2['footprint'],len(known),report2['prepared_regions'])
if __name__=='__main__':unittest.main(verbosity=2)

