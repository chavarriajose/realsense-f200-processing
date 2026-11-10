#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# build_macos_app.sh
#
# Builds "RealSense Depth Server.app": a double-click app for Mac users that
# contains the depth server and everything it needs (Python, numpy, OpenCV,
# libusb, ...). People who download the app install nothing else.
#
# For developers only. You do not need this script to use the app.
#
# Usage (from the main project folder, on a Mac):
#   tools/macos/build_macos_app.sh
#
# Result:
#   dist/RealSense Depth Server.app
#   dist/RealSense-Depth-Server-macOS.zip    (the file to share)
#
# The app is "universal": it runs on Apple Silicon Macs (M1 and newer) and on
# Intel Macs. To make that possible we need a Python that is universal itself
# (the installer from python.org is; the Homebrew one is not), and every
# compiled package for both kinds of processor, glued together.
#
# What you need once:
#   - Python 3.14 from https://www.python.org/downloads/macos/ ("universal2"
#     installer). To use another universal Python, set PYTHON=... on the
#     command line; the script asks it for its version number.
#   - An internet connection (the script downloads packages with pip).
#
# Everything the script downloads or builds goes into the folder .build/,
# which git ignores. Delete it to start from scratch.

set -e

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"
BUILD="$PROJECT/.build"
DIST="$PROJECT/dist"
APP_NAME="RealSense Depth Server"
APP="$DIST/$APP_NAME.app"

cd "$PROJECT"

# --- 1. Check the Python -------------------------------------------------
if [ ! -x "$PYTHON" ]; then
  echo "Python not found at $PYTHON"
  echo "Install the universal2 Python 3.14 from python.org, or set PYTHON=..."
  exit 1
fi
ARCHS="$(lipo -archs "$(dirname "$PYTHON")/../Python" 2>/dev/null || true)"
if [[ "$ARCHS" != *arm64* || "$ARCHS" != *x86_64* ]]; then
  echo "This Python is not universal (it only has: $ARCHS)."
  echo "Please use the universal2 installer from python.org."
  exit 1
fi
# Packages are downloaded for exactly this Python version (for example 3.14).
PY_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
echo "1/6 Using universal Python $PY_VERSION at $PYTHON"

# --- 2. A separate build environment -------------------------------------
# We do not touch .venv (used to run the server from a terminal).
if [ ! -x "$BUILD/venv/bin/python" ]; then
  "$PYTHON" -m venv "$BUILD/venv"
fi
"$BUILD/venv/bin/pip" install -q --upgrade pip
# Pure Python packages work on both processors as they are.
# The version numbers are fixed (pinned) so the build gives the same result
# every time. These are the versions the app was tested with. When you
# update them, test the app again on a real camera.
"$BUILD/venv/bin/pip" install -q pyinstaller==6.22.3 delocate==0.13.0 \
  websockets==17.4 python-osc==1.10.2 libusb1==3.4.0
echo "2/6 Build environment ready"

# --- 3. Universal numpy and OpenCV ------------------------------------------
# These packages contain compiled code. Their makers publish one version for
# Apple Silicon (arm64) and one for Intel (x86_64). We download both and glue
# them into one "universal2" package with delocate-merge.
# Good to know: OpenCV brings its own copies of some helper libraries, and
# the two versions do not always use the same ones. delocate-merge then
# keeps both sets side by side (one only for arm64, one only for x86_64).
# That is expected: each processor loads its own set.
rm -rf "$BUILD/wheels"
for arch in arm64 x86_64; do
  "$BUILD/venv/bin/pip" download -q --only-binary=:all: --no-deps \
    --platform "macosx_14_0_$arch" --python-version "$PY_VERSION" --implementation cp \
    -d "$BUILD/wheels/$arch" \
    numpy==2.5.4 opencv-python-headless==5.0.0.93 libusb-package==1.0.30.1
done
mkdir -p "$BUILD/wheels/universal2"
for package in numpy opencv_python_headless; do
  "$BUILD/venv/bin/delocate-merge" \
    "$(ls "$BUILD/wheels/arm64/$package"-*.whl)" \
    "$(ls "$BUILD/wheels/x86_64/$package"-*.whl)" \
    -w "$BUILD/wheels/universal2"
done
"$BUILD/venv/bin/pip" install -q --no-deps --force-reinstall "$BUILD/wheels/universal2/"*.whl
echo "3/6 Universal numpy and OpenCV installed"

# --- 4. Universal libusb ------------------------------------------------------
# libusb is the small C library that talks to USB devices. The libusb-package
# project publishes ready-made copies for each processor. We unpack both and
# glue them together with Apple's "lipo" tool. The usb1 package looks for a
# file called libusb-1.0.dylib in its own folder first, so we put it there.
rm -rf "$BUILD/libusb"
for arch in arm64 x86_64; do
  mkdir -p "$BUILD/libusb/$arch"
  unzip -q -o "$(ls "$BUILD/wheels/$arch/libusb_package"-*.whl)" -d "$BUILD/libusb/$arch"
done
SITE_PACKAGES="$("$BUILD/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
lipo -create \
  "$BUILD/libusb/arm64/libusb_package/libusb-1.0.dylib" \
  "$BUILD/libusb/x86_64/libusb_package/libusb-1.0.dylib" \
  -output "$SITE_PACKAGES/usb1/libusb-1.0.dylib"
echo "4/6 Universal libusb: $(lipo -archs "$SITE_PACKAGES/usb1/libusb-1.0.dylib")"

# --- 5. Freeze the server with PyInstaller ----------------------------------
# PyInstaller collects Python and every package the server uses into one
# folder, with a program called "depth-server" inside.
#   --exclude-module capture_linux:       Linux only, not needed on a Mac
#   --exclude-module websockets.speedups: an optional speed-up that is only
#                                         published for one processor; the
#                                         package works fine without it
rm -rf "$BUILD/pyinstaller"
"$BUILD/venv/bin/pyinstaller" --noconfirm --log-level WARN \
  --onedir --console --target-arch universal2 \
  --name depth-server \
  --distpath "$BUILD/pyinstaller/dist" --workpath "$BUILD/pyinstaller/work" \
  --specpath "$BUILD/pyinstaller" \
  --paths "$PROJECT/server" \
  --add-data "$PROJECT/server/config.toml:." \
  --exclude-module capture_linux --exclude-module websockets.speedups \
  "$PROJECT/server/depth_server.py"
echo "5/6 Server frozen"

# --- 6. Put the app together --------------------------------------------------
# A Mac app is just a folder with a special layout:
#   Contents/Info.plist             name and settings of the app
#   Contents/MacOS/launcher         what runs on double click
#   Contents/Resources/...          everything else
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$PROJECT/tools/macos/macos_app/Info.plist" "$APP/Contents/Info.plist"
cp "$PROJECT/tools/macos/macos_app/launcher.sh" "$APP/Contents/MacOS/launcher"
cp "$PROJECT/tools/macos/macos_app/start-server.command" "$APP/Contents/Resources/"
cp -R "$BUILD/pyinstaller/dist/depth-server" "$APP/Contents/Resources/"
chmod +x "$APP/Contents/MacOS/launcher" "$APP/Contents/Resources/start-server.command"

# The licenses travel with the app, as open source licenses ask: our own
# (LICENSE.txt) and those of every part inside it (licenses/). This has to
# happen before the signature below, which covers every file in the app.
cp "$PROJECT/LICENSE" "$APP/Contents/Resources/LICENSE.txt"
"$BUILD/venv/bin/python" "$PROJECT/tools/collect_licenses.py" "$APP/Contents/Resources/licenses" \
  numpy opencv-python-headless websockets python-osc pyinstaller libusb1

# Give the whole app an "ad-hoc" signature. It is not a real Apple Developer
# signature (that costs money), but it keeps macOS from reporting the app as
# "damaged". People still need to allow it once, see docs/macos/setup.md.
# (codesign prints "replacing existing signature" for files PyInstaller
# already signed; that is normal.)
codesign --force --deep --sign - "$APP"

# ditto makes a zip that keeps everything a Mac app needs.
rm -f "$DIST/RealSense-Depth-Server-macOS.zip"
ditto -c -k --keepParent "$APP" "$DIST/RealSense-Depth-Server-macOS.zip"
echo "6/6 Done:"
echo "    $APP"
echo "    $DIST/RealSense-Depth-Server-macOS.zip ($(du -h "$DIST/RealSense-Depth-Server-macOS.zip" | cut -f1))"
