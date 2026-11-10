#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# start-server.sh
#
# Starts the depth server and keeps its window open, so you can read the
# address to use in sketches. The "RealSense Depth Server" icon runs this
# file (see tools/linux/install_launcher.sh). Double clicking this file in the
# Files app only shows its text: use the icon instead, or a terminal:
#     ./start-server.sh
#
# To stop the server, close the window or press Ctrl+C.

# Work from the project folder, wherever this file was started from.
cd "$(dirname "$0")"

# Keep the window open at the end, so any message can still be read.
wait_before_closing() {
  echo
  read -r -p "Press Enter to close this window."
}

if [ ! -x .venv/bin/python ]; then
  echo "The Python environment (.venv) is missing."
  echo "Please follow step 4 in docs/linux/setup.md first."
  wait_before_closing
  exit 1
fi

# If the server already runs in the background as a service, a second one
# could not use the camera. Show where to find it instead.
if systemctl is-active --quiet realsense-depth 2>/dev/null; then
  echo "The depth server is already running in the background (as a service)."
  echo "Sketches can use: String SERVER = \"auto\";"
  echo "or one of these addresses: $(hostname).local  $(hostname -I)"
  wait_before_closing
  exit 0
fi

.venv/bin/python -u server/depth_server.py
wait_before_closing
