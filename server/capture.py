# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capture.py

Picks the right camera code for the computer we are running on, so the rest
of the project can simply write:

    from capture import F200Camera, NO_DEPTH

  * Linux:   capture_linux.py   (uses the normal Linux video driver)
  * macOS:   capture_macos.py   (talks to the camera over USB, needs sudo)
  * Windows: capture_windows.py (uses Windows' own video system, Media Foundation)

All three files offer the same interface: F200Camera, Frames, NO_DEPTH and
DEPTH_UNITS_PER_MM.
"""

import sys

if sys.platform == "darwin":
    # "darwin" is the name Python uses for macOS.
    from capture_macos import (  # noqa: F401
        DEPTH_UNITS_PER_MM, NO_DEPTH, F200Camera, Frames)
elif sys.platform.startswith("linux"):
    from capture_linux import (  # noqa: F401
        DEPTH_UNITS_PER_MM, NO_DEPTH, F200Camera, Frames)
elif sys.platform == "win32":
    # "win32" is the name Python uses for Windows, also on 64-bit Windows.
    from capture_windows import (  # noqa: F401
        DEPTH_UNITS_PER_MM, NO_DEPTH, F200Camera, Frames)
else:
    raise RuntimeError(
        f"Sorry, this operating system ({sys.platform}) is not supported yet. "
        "The depth server runs on Linux, macOS and Windows.")
