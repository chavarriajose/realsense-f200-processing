# RealSense F200 for Processing

Bring an old Intel RealSense F200 depth camera (also sold by Creative as
model VF0800) back to life and use it from Processing.

> **Beta, version 0.9.0.** Works on Linux, macOS and Windows. So far it has
> been tested on one computer of each kind. Please try it and
> [tell us how it went](CONTRIBUTING.md#report-a-problem-or-share-how-it-went),
> good or bad.

The camera is plugged into a computer that runs a small server: a Linux
computer that several people share, or your own Mac or Windows PC. Your
Processing sketches, on that computer or any other one in the same network,
receive the depth image and some handy values from the server. You never
install camera drivers.

```
[F200 camera] --USB 3.0--> [Linux, Mac or Windows: depth server] --network--> [Processing sketches]
```

What you get:

- **Depth images** over WebSocket: a ready to show grayscale picture, and
  the exact distance in millimeters for every pixel. Infrared and color
  images too, if you switch them on.
- **Simple values** over OSC: the nearest point, whether something is there,
  the biggest blob (like a hand) and the average distance. OSC works with
  Processing, Max, Pure Data, TouchDesigner and many more.
- **Five Processing examples**, from "show the depth image" to a 3D point cloud.

## Start here

**1. Start the depth server** on the computer the camera is plugged into:

| Your camera is plugged into... | What you do | Guide |
|--------------------------------|-------------|-------|
| **Windows** | download `RealSense-Depth-Server-Windows.zip` from [Releases](https://github.com/chavarriajose/realsense-f200-processing/releases), extract it, double-click **RealSense Depth Server**. No driver, no password. | [docs/windows/setup.md](docs/windows/setup.md) |
| **macOS** | download `RealSense-Depth-Server-macOS.zip` from [Releases](https://github.com/chavarriajose/realsense-f200-processing/releases), open the app, type your Mac password. | [docs/macos/setup.md](docs/macos/setup.md) |
| **Linux** | a few terminal commands (below), then a desktop icon or automatic start at boot. | [docs/linux/setup.md](docs/linux/setup.md) |

**2. Run your first sketch**: install Processing 4, open
`processing/example01_show_depth` and press Run. The sketch finds the server
on the network by itself (`String SERVER = "auto";`). Step by step, for Mac,
Windows and Linux: [docs/first-sketch.md](docs/first-sketch.md).

The quick version for Linux (Ubuntu 24.04 LTS or newer, camera in a USB 3.0
port):

```bash
sudo apt update
sudo apt install git python3-opencv python3-numpy python3-websockets python3-venv v4l-utils
git clone https://github.com/chavarriajose/realsense-f200-processing.git
cd realsense-f200-processing
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-linux.txt
./start-server.sh
```

## Folders

| Folder        | What is inside                                                    |
|---------------|-------------------------------------------------------------------|
| `docs/`       | the guides: one folder each for `linux/`, `macos/` and `windows/`, plus the first sketch and the message format |
| `processing/` | the example sketches for Processing 4                             |
| `server/`     | the depth server (Python) and its settings, `config.toml`         |
| `tools/`      | the live camera preview, a test client, and in `linux/`, `macos/` and `windows/` the scripts that build the ready-made programs |

## Tested on

| System | Computer | Processing |
|--------|----------|------------|
| Linux | Ubuntu 24.04 LTS, 64-bit PC | 4.5.7 |
| macOS | macOS 26 on Apple Silicon (the Intel part of the app only through Rosetta) | 4.5.7 |
| Windows | Windows 11, 64-bit, through a USB 3.0 hub | 4.3 |

Each one was checked with a real F200: depth, infrared and color images,
the OSC values, all five examples, and starting and stopping the server.

## Known limitations

- **Beta:** each system was tested on one computer. Other computers, USB
  ports and hubs may behave differently. Windows 10 and Intel Macs should
  work but were not tried on real hardware.
- **Mac:** the server needs your Mac password (administrator rights) to use
  the camera, see [docs/macos/setup.md](docs/macos/setup.md).
- **First start:** the Mac app and the Windows program are not signed with a
  paid certificate, so the system warns you once. The guides show the one
  click it takes.
- **Range:** the F200 measures from about 20 cm to about 1.2 m and works best
  within about 80 cm. Dark or shiny surfaces may give no depth.
- **Color is not aligned with depth:** the color camera sits next to the
  depth camera, so the two pictures are a little shifted.
- **Many sketches on Wi-Fi:** each sketch receiving exact depth (`depth16`)
  uses about 1.4 MB per second, the grayscale picture (`depth8`) about
  0.6 MB per second.
- **Windows on ARM** and Raspberry Pi are not supported (yet).

## Good to know

- It needs a USB 3.0 port. A USB 3.0 hub or USB-C adapter works fine. The
  standard Linux and Windows drivers support the camera, so no special
  camera software is needed there; on a Mac the server talks to the camera
  over USB itself.
- Distances are in millimeters. The conversion from the camera's units is
  one number, `DEPTH_UNITS_PER_MM` in `server/capture_linux.py` (and the
  same in `server/capture_macos.py` and `server/capture_windows.py`).
- Writing your own client (p5.js, Python, Max, ...)?
  [docs/protocol.md](docs/protocol.md) describes every message byte by byte.

## How this was made

RealSense F200 for Processing is made by **Jose Chavarria**.

The code, the documentation and the tests were written with the help of an
AI coding agent, **Claude Code** (by Anthropic).

If something looks wrong or could be explained better, please
[open an issue](https://github.com/chavarriajose/realsense-f200-processing/issues).

## Share your improvements

This is an open source project, and it gets better when people share back.
If you fix something, add support for another computer, write an example or
translate a guide, please send it back so everyone with an F200 can use it.
[CONTRIBUTING.md](CONTRIBUTING.md) explains how, also for people who have
never done this before.

## License

Copyright (C) 2026 Jose Chavarria. 

- **The depth server, the tools and the guides** are under the
  [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0).
  You can use, study, change and share them freely. If you share a changed
  version, or let other people use a changed version over a network, you
  must also share its source code under the same license. That way
  improvements stay open for everyone.
- **The Processing examples** (`processing/`) are under the
  [MIT license](processing/LICENSE). Use them freely as a starting point for
  your own sketches and artworks, with no duty to share your sketch.

The ready-made Mac app and Windows program contain other open source parts,
each under its own license: see
[docs/third-party-licenses.md](docs/third-party-licenses.md).

## Credits

The depth format and the depth scale come from Intel's open source
[librealsense v1](https://github.com/IntelRealSense/librealsense/tree/v1.12.4)
(Apache 2.0), which supported the F200. This project does not use or include
it; it only learned from it.
