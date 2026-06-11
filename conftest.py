"""Pytest bootstrap — ensure the project root is importable so tests can
`from backend.services... import ...` regardless of where pytest is invoked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
