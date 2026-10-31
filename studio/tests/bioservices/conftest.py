"""Make the repository root importable for the bioservices tests.

The bioservices packages (`connectors`, `experiments`) live at the repository
root and are not installed into the test environment, so the root is placed on
`sys.path` here rather than depending on how pytest was invoked.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
