import sys
from pathlib import Path

# The backend modules import each other by name, as they do when app.py runs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
