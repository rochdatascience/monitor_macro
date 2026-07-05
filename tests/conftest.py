"""Coloca src/ no sys.path para importar os pipelines como no runtime."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
