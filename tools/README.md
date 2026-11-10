# tools

Small helper programs. Most people only need `preview.py`, to check that the
camera works before starting the server.

| Where             | What is inside                                                  |
|-------------------|-----------------------------------------------------------------|
| `preview.py`      | live camera preview (Linux, Mac and Windows)                    |
| `test_client.py`  | checks the server without Processing (any computer)             |
| `linux/`          | builds the Linux download, desktop icon for the server, first test script, sketch tests |
| `macos/`          | builds the Mac app, sketch tests on a Mac                       |
| `windows/`        | builds the Windows program, sketch tests on Windows             |
| `collect_licenses.py` | used by the build scripts: puts all license texts into the program |

All commands below are typed in a terminal, from the main project folder
(the folder that contains `README.md` and the `server` folder).

## preview.py: live camera preview

Shows depth, infrared and color side by side in a window.

### On Linux

The preview needs a few system packages. Install them once (this asks for your
password, because `sudo` installs software for the whole computer):

```bash
sudo apt install python3-opencv python3-numpy v4l-utils
```

Then start the preview:

```bash
python3 tools/preview.py
```

What you should see:

- A window called "RealSense F200 preview" with three pictures.
- Left: depth. Things close to the camera are bright, things further away are
  darker, and places where the camera could not measure are black.
- Middle: infrared (a black and white picture that also works in the dark).
- Right: the normal color picture.
- In the top left corner, the distance at the center of the image, for
  example `center: 640 mm`.

Press `s` to save a screenshot (`preview.png`) and `q` to quit.

If you see `Could not find the RealSense F200 depth camera`, check that the
camera is plugged into a USB 3.0 port (often blue inside) and run
`v4l2-ctl --list-devices` to see whether Linux found it.

The preview and the server cannot use the camera at the same time. Stop the
server before you start the preview.

### On a Mac

The preview also works with the camera plugged into a Mac. Prepare once
(you need [Homebrew](https://brew.sh); these commands do not ask for a
password):

```bash
brew install libusb
python3 -m venv .venv
.venv/bin/pip install -r requirements-macos.txt
```

Then start the preview with `sudo` in front. It asks for your Mac password,
because macOS only lets administrators take the camera away from its own
driver (nothing appears while you type the password, that is normal):

```bash
sudo .venv/bin/python tools/preview.py
```

You should see the same window as described above. The server must not be
running at the same time: if it is, the preview says `The camera is busy`.
If you forget `sudo`, it tells you to add it.

### On Windows

The preview also works with the camera plugged into a Windows PC. You need
64-bit Python 3.11 or newer from https://www.python.org/downloads/windows/ .
Prepare once, in PowerShell, from the main project folder (no administrator
rights needed):

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements-windows.txt
```

Then start the preview:

```
.venv\Scripts\python tools\preview.py
```

You should see the same window as described above. The server must not be
running at the same time: if it is, the preview says `The camera is busy`.
(On Windows, `.venv\Scripts\python` takes the place of `.venv/bin/python`
in the other commands on this page too.)

## test_client.py: check the server without Processing

Connects to the depth server like a sketch would and saves what it receives.
It needs the same Python setup as the server ("Before you start" in
`server/README.md`), which is why it runs with `.venv/bin/python`.
Start the server first (see `server/README.md`), then in a second terminal:

```bash
.venv/bin/python tools/test_client.py 127.0.0.1 depth8 depth16 values osc
```

Use the server's IP address instead of `127.0.0.1` when you run it on
another computer. After 5 seconds it prints how many messages arrived for
each stream (about 15 per second), the latest values, and saves the last
image of each stream as `test_depth8.png`, `test_depth16.png` and so on.

## Linux tools (`tools/linux/`)

### install_launcher.sh: a desktop icon for the server

Adds a "RealSense Depth Server" icon to the desktop and the app menu, so the
server starts with a double click instead of a terminal command. Run it
once (no password needed):

```bash
tools/linux/install_launcher.sh
```

It ends with `Done. Double click "RealSense Depth Server" on the desktop to
start the server.` The icon runs `start-server.sh` (in the main project
folder) in a terminal window that shows what to write in sketches. Run it
again if you move the project folder.

### view_depth.py: the very first test

The script that first proved the camera works on Linux. It shows a depth
frame that was recorded to a file with `v4l2-ctl`. The instructions are at
the top of the file. You do not need it for normal use; `preview.py` is easier.

### run_sketch_headless.sh: test the Processing examples on Linux

For developers. Runs one Processing example without a screen, against a
server on this computer, and saves a screenshot. You do not need this to use the project.

Prepare once (these files are not part of the repository, the folder
`.tools/` is ignored by git):

1. Install the "pretend screen": `sudo apt install xvfb`
2. Download "Processing 4 for Linux, portable" (the `linux-x64-portable.zip`
   file) from https://github.com/processing/processing4/releases and unzip
   it so that `.tools/Processing/bin/Processing` exists.
3. Download `oscP5-0.9.9.zip` from https://github.com/sojamo/oscp5/releases
   and unzip it so that `.tools/home/sketchbook/libraries/oscP5/library/oscP5.jar`
   exists.

Then, with the server running in another terminal:

```bash
tools/linux/run_sketch_headless.sh processing/example01_show_depth example01.png
```

The last line should be `OK: /full/path/to/example01.png`. If the sketch
could not save a screenshot (for example because the server is not running)
it prints `FAILED: no screenshot saved` instead.

### build_linux_bundle.sh: build the Linux download

For developers. Builds `dist/RealSense-Depth-Server-Linux-x64.tar.gz`: the
server with everything it needs, a start script and a one-time desktop icon
installer (the files in `tools/linux/linux_bundle/`). It needs Python 3.11 or
newer with the venv module and an internet connection:

```bash
tools/linux/build_linux_bundle.sh
```

It counts its steps from `1/5` to `5/5`. The download only works on Linux
versions about as new as the one it was built on, or newer.

## Mac tools (`tools/macos/`)

### build_macos_app.sh: build the Mac app

For developers. Builds `dist/RealSense Depth Server.app` and the zip file to
share (`dist/RealSense-Depth-Server-macOS.zip`, about 110 MB). The app
contains the server with everything it needs, for Apple Silicon and Intel
Macs. It needs the universal2 Python 3.14 from python.org and an internet
connection; the top of the script explains why.

```bash
tools/macos/build_macos_app.sh
```

It counts its steps from `1/6` to `6/6` and ends with the paths of the app
and the zip. `docs/macos/setup.md` explains how to open the app.

### run_sketch_macos.sh: test the Processing examples on a Mac

For developers. Runs one Processing example on a Mac against a running
server and saves a screenshot. It needs Processing 4 in `/Applications`
and, for example 05, the oscP5 library (from the Contribution Manager).
The sketch window opens for a few seconds and closes by itself.

```bash
tools/macos/run_sketch_macos.sh processing/example01_show_depth example01.png
```

The sketch finds the server by itself (`"auto"`). To test a typed address
instead, put `SERVER=127.0.0.1` in front of the command. The last line
should be `OK: /full/path/to/example01.png`.

## Windows tools (`tools/windows/`)

### build_windows_exe.ps1: build the Windows program

For developers. Builds `dist\RealSense Depth Server\RealSense Depth Server.exe`
and the zip file to share (`dist\RealSense-Depth-Server-Windows.zip`, about
60 MB). The program contains the server with everything it needs, for 64-bit
Windows 10 and 11. It needs 64-bit Python 3.11 or newer from python.org and
an internet connection. In PowerShell, from the main project folder:

```
powershell -ExecutionPolicy Bypass -File tools\windows\build_windows_exe.ps1
```

("-ExecutionPolicy Bypass" lets Windows run this one script without changing
any setting.) It counts its steps from `1/5` to `5/5` and ends with the paths
of the program and the zip. `docs/windows/setup.md` explains how to start it.

### run_sketch_windows.ps1: test the Processing examples on Windows

For developers. Runs one Processing example on a Windows PC against a
running server and saves a screenshot. It looks for Processing 4's
`processing-java.exe` in the usual places (also an unzipped copy in your
Documents, Downloads or Desktop folder); for example 05 it also needs the
oscP5 library. The sketch window opens for a few seconds and closes by
itself. In PowerShell:

```
powershell -ExecutionPolicy Bypass -File tools\windows\run_sketch_windows.ps1 processing\example01_show_depth example01.png
```

The sketch finds the server by itself (`"auto"`). To test a typed address
instead, add `-Server 127.0.0.1`. If Processing is somewhere else, add
`-Processing "C:\path\to\processing-java.exe"`. The last line should be
`OK: C:\full\path\to\example01.png`.

## Building all downloads on GitHub

You do not need a Mac, a Linux computer and a Windows PC to make the
downloads: GitHub builds all three on its own computers, with the scripts
above (see `.github/workflows/build-downloads.yml`).

- **To test:** on the project page, open **Actions**, choose
  **Build downloads** and click **Run workflow**. After about 10 minutes the
  three files are at the bottom of that run's page, under **Artifacts**.
  Nothing is published.
- **For a release:** push a version tag, for example `git tag v1.0.0`
  and `git push origin v1.0.0`. The files are then attached to the
  release with that name (a draft pre-release is made if it does not exist
  yet, ready for you to write the notes and publish).

GitHub's computers have no camera: each build only checks that the program
starts. Try each download once with a real F200 before calling it tested.
