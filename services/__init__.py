"""Service package bootstrap.

Ensures the generated protobuf modules directory is on sys.path so that
imports like ``import common_pb2`` inside the generated code succeed.
"""

from pathlib import Path
import sys

GENERATED_DIR = Path(__file__).resolve().parents[1] / "generated"
GEN_PATH = str(GENERATED_DIR)

if GENERATED_DIR.exists() and GEN_PATH not in sys.path:
    sys.path.append(GEN_PATH)

