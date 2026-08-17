"""Make the HiQS package importable without an editable install."""

from pathlib import Path
import sys


HIQS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIQS_ROOT))
