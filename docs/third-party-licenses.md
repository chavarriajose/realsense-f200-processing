# Third-party software

The project's own code is under the AGPL-3.0 (server and tools) and the MIT
license (Processing examples), see the main [README](../README.md#license).

The ready-made **Mac app** and **Windows program** also contain other open
source software, so that nobody has to install it separately. Each part
keeps its own license:

| Part | What it does here | License | Where |
|------|-------------------|---------|-------|
| Python | runs the server | PSF License | Mac app, Windows program |
| NumPy | works with the images as arrays of numbers | BSD 3-Clause | Mac app, Windows program |
| OpenCV (`opencv-python-headless`) | image processing, JPEG, blob detection | Apache 2.0 | Mac app, Windows program |
| websockets | sends the images | BSD 3-Clause | Mac app, Windows program |
| python-osc | sends the OSC values | The Unlicense | Mac app, Windows program |
| libusb | talks to the camera over USB on a Mac | LGPL 2.1 or later | Mac app only |
| libusb1 (Python package `usb1`) | Python access to libusb | LGPL 2.1 or later | Mac app only |
| PyInstaller (its start-up code) | packs everything into one app or program | GPL 2.0 with an exception that allows this use | Mac app, Windows program |

The license texts of all these parts travel with the program: in the
`licenses` folder next to `RealSense Depth Server.exe` on Windows, and in
`Contents/Resources/licenses` inside the Mac app (right-click the app, **Show
Package Contents**). The build scripts collect them with
`tools/collect_licenses.py`. The source code of each part is available from
its project's website.

The OpenCV package also contains parts of other projects, for example
FFmpeg (LGPL); they are listed in OpenCV's `LICENSE-3RD-PARTY.txt` in the
`licenses` folder.

When you run the server from a terminal instead (see the "For developers"
parts of the setup guides), pip installs the same packages with their
licenses into your own `.venv` folder.

The Processing examples use these libraries, which you install yourself
from Processing:

| Library | License |
|---------|---------|
| Processing core | LGPL 2.1 |
| oscP5 (example 05 only) | LGPL 2.1 |

## Learned from, not included

The depth format and the depth scale were learned from Intel's open source
[librealsense v1](https://github.com/IntelRealSense/librealsense/tree/v1.12.4)
(Apache 2.0), which supported the F200. No code from it is included.
