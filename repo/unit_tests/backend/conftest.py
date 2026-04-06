"""Shared fixtures for backend unit tests.

These tests run without a database connection.
"""

import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
