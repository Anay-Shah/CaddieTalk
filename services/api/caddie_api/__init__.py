"""CaddieTalk HTTP API.

Runs as a local dev server now; wrapped for Lambda in M4.
"""

from .app import app

__all__ = ["app"]
