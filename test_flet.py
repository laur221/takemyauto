#!/usr/bin/env python3
"""Test Flet installation and image handling"""

import sys

print(f"Python version: {sys.version}")
try:
    import flet as ft
    ver = getattr(ft, '__version__', 'unknown')
    print(f"Flet version: {ver}")

    # Test Image widget creation
    img = ft.Image(
        src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        width=100,
        height=100
    )
    print(f"SUCCESS: Image created: {img}")

except ImportError:
    print("ERROR: Flet not installed. Run: pip install flet>=0.20.0")
    raise SystemExit(1)
except Exception as e:
    print(f"ERROR: {e}")
    raise SystemExit(1)
