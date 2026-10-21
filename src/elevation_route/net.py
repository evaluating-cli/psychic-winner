"""
Shared HTTP session for all outbound requests (geocoding + tile downloads).
"""

from __future__ import annotations

import requests

from . import __version__

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": f"elevation-route-tool/{__version__}"})
