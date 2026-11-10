#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# build_linux_bundle.sh
#
# Builds the ready-made Linux download: a folder with the depth server and
# everything it needs (Python, numpy, OpenCV, ...), so people who download
# it install nothing else.
#
# For developers only. You do not need this script to use the program.
# GitHub builds the download automatically for every release
# (see .github/workflows/build-downloads.yml).
#
# Usage (from the main project folder, on a 64-bit Intel/AMD Linux computer):
#   tools/linux/build_linux_bundle.sh
#
# Result:
#   dist/RealSense Depth Server/                     the program folder
#   dist/RealSense-Depth-Server-Linux-x64.tar.gz     the file to share
#
# What you need once:
#   - Python 3.11 or newer with the venv module
#     (on Ubuntu: sudo apt install python3-venv). To use a specific Python,
#     set PYTHON=..., for example: PYTHON=python3.13 tools/linux/build_linux_bundle.sh
#   - An internet connection (the script downloads packages with pip).
#
# The program only runs on Linux versions about as new as the one it was
# built on, or newer (it uses the system's C library). Building on an older
# Linux, like the GitHub build does, makes it work on more computers.
#
# Everything the script downloads or builds goes into the folder .build/linux,
# which git ignores. Delete it to start from scratch.

set -e

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
BUILD="$PROJECT/.build/linux"
DIST="$PROJECT/dist"
APP_FOLDER="$DIST/RealSense Depth Server"
ARCHIVE="$DIST/RealSense-Depth-Server-Linux-x64.tar.gz"

cd "$PROJECT"

# --- 1. Check the Python -----------------------------------------------------
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "Please use Python 3.11 or newer (set PYTHON=...). Found: $("$PYTHON" --version 2>&1)"
  exit 1
fi
echo "1/5 Using $("$PYTHON" --version) at $(command -v "$PYTHON")"

# --- 2. A separate build environment -------------------------------------
# We do not touch .venv (used to run the server from a terminal).
if [ ! -x "$BUILD/venv/bin/python" ]; then
  "$PYTHON" -m venv "$BUILD/venv"
fi
# The version numbers are fixed (pinned), also for the helpers PyInstaller
# uses, so the build gives (almost) the same result every time. They match
# the Windows build. When you update them, test again with a real camera.
# opencv-python-headless is the smaller OpenCV without windows, which is all
# the server needs.
"$BUILD/venv/bin/python" -m pip install -q pip==26.3
"$BUILD/venv/bin/python" -m pip install -q \
  pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.10 altgraph==0.17.5 \
  numpy==2.5.4 opencv-python-headless==5.0.0.93 websockets==17.4 python-osc==1.10.2
echo "2/5 Build environment ready"

# --- 3. Freeze the server with PyInstaller -----------------------------------
# PyInstaller collects Python and every package the server uses into one
# folder, with the program "realsense-depth-server" inside.
#   --exclude-module capture_macos / capture_windows / usb1:
#               the camera code for the other systems, not needed here
rm -rf "$BUILD/pyinstaller"
"$BUILD/venv/bin/python" -m PyInstaller --noconfirm --log-level WARN \
  --onedir --console --name realsense-depth-server \
  --distpath "$BUILD/pyinstaller/dist" --workpath "$BUILD/pyinstaller/work" \
  --specpath "$BUILD/pyinstaller" \
  --paths "$PROJECT/server" \
  --add-data "$PROJECT/server/config.toml:." \
  --exclude-module capture_macos --exclude-module capture_windows \
  --exclude-module usb1 \
  "$PROJECT/server/depth_server.py"
echo "3/5 Server frozen"

# --- 4. Put the program folder together -----------------------------------
#   realsense-depth-server, _internal/   the program (from PyInstaller)
#   start-server.sh                      starts it and keeps the window open
#   install-desktop-icon.sh              adds the desktop icon, once
#   READ ME FIRST.txt                    the short instructions
#   LICENSE.txt, licenses/               our license and those of every part
rm -rf "$APP_FOLDER"
mkdir -p "$APP_FOLDER"
cp -R "$BUILD/pyinstaller/dist/realsense-depth-server/." "$APP_FOLDER/"
cp "$PROJECT/tools/linux/linux_bundle/start-server.sh" \
   "$PROJECT/tools/linux/linux_bundle/install-desktop-icon.sh" \
   "$PROJECT/tools/linux/linux_bundle/READ ME FIRST.txt" "$APP_FOLDER/"
chmod +x "$APP_FOLDER/realsense-depth-server" "$APP_FOLDER/start-server.sh" \
  "$APP_FOLDER/install-desktop-icon.sh"
cp "$PROJECT/LICENSE" "$APP_FOLDER/LICENSE.txt"
"$BUILD/venv/bin/python" "$PROJECT/tools/collect_licenses.py" "$APP_FOLDER/licenses"
echo "4/5 Program folder ready"

# --- 5. Pack it ----------------------------------------------------------------
# A .tar.gz keeps the "this file is a program" marks (a .zip may lose them).
# Ubuntu's Files app unpacks it with a double click.
rm -f "$ARCHIVE"
tar -czf "$ARCHIVE" -C "$DIST" "RealSense Depth Server"
echo "5/5 Done:"
echo "    $APP_FOLDER/realsense-depth-server"
echo "    $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
