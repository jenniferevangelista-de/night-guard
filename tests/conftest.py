"""Test setup: never send anything to Sentry or Auth0 while testing, and use a fixed parent list."""
import os
import sys
from pathlib import Path

os.environ["SENTRY_DSN"] = ""            # load_env() only fills missing keys, so this stays empty
os.environ["AUTH0_CLIENT_SECRET"] = ""
os.environ["PARENT_EMAILS"] = "parent@example.test"
os.environ.setdefault("NG_BACKEND", "ollama")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
