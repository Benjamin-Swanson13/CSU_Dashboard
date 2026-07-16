"""Production entry point for Render/Gunicorn.

The full dashboard implementation lives in app2.py. Keeping this wrapper small
prevents the old CSV/import path from being used when Render runs app:server.
"""

from app2 import app, server


__all__ = ["app", "server"]
