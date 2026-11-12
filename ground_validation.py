"""Reuse a nearby native ground calibration; terrain is revalidated on load."""
import json,math
from pathlib import Path
def load_anchor(path,assets,position):
 try:
  doc=json.loads(Path(path).read_text());anchor=doc['position']
  if doc['assets']!=str(Path(assets).resolve()):return None
  if len(anchor)!=3 or not all(math.isfinite(x) for x in anchor):return None
  if math.dist(anchor,position)>64:return None
  if not doc['ground_match_required'] or not math.isfinite(doc['native_height_error']) or abs(doc['native_height_error'])>.2:return None
  return anchor
 except (OSError,ValueError,KeyError,TypeError):return None
def save_anchor(path,assets,report):
 report=report.get('ground_validation_anchor',report)
 if not report.get('ground_match_required') or not math.isfinite(report.get('native_height_error',999)) or abs(report.get('native_height_error',999))>.2:return False
 anchor=report.get('position',[])
 if len(anchor)!=3 or not all(math.isfinite(v) for v in anchor):return False
 Path(path).write_text(json.dumps(dict(report,assets=str(Path(assets).resolve())),indent=2))
 return True
