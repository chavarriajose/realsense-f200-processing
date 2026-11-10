#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# start-server.command
#
# This file lives inside "RealSense Depth Server.app". When you open the app,
# it opens this file in a Terminal window. It asks for your Mac password
# (macOS only lets administrators take the camera away from its own webcam
# driver) and then runs the depth server.
#
# To stop the server, close the window or press Ctrl+C.

# The server program sits next to this file, inside the app.
HERE="$(cd "$(dirname "$0")" && pwd)"

clear
echo "================================================================"
echo "  RealSense Depth Server"
echo
echo "  macOS needs your password to let this program use the camera."
echo "  Type your Mac password and press Enter."
echo "  (You will not see the letters while you type. That is normal.)"
echo "================================================================"
echo

sudo "$HERE/depth-server/depth-server"

# Keep the window open at the end, so any message can still be read.
echo
read -r -p "Press Enter to close this window."
