"""Vercel Serverless Function entrypoint for JurisGuide.

Imports and exposes the FastAPI `app` instance from app.py.
Preserves existing project layout for local execution and Render compatibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so all application modules are discoverable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app  # noqa: E402
