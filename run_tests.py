"""Run the portable regression suite; real game assets remain optional."""
import sys, unittest
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'tests'),str(root)]
if __name__=='__main__':
    suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
