"""Put the plugin folder on sys.path so tests can import prescriptive."""

import os
import sys

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN not in sys.path:
    sys.path.insert(0, PLUGIN)
