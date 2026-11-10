#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# start-server.sh (inside the ready-made Linux download)
#
# Starts the depth server and keeps its window open at the end, so any
# message can still be read. The "RealSense Depth Server" icon runs this
# file (see install-desktop-icon.sh). From a terminal, in this folder:
#     ./start-server.sh
#
# To stop the server, close the window or press Ctrl+C.

# Work from this folder, wherever the file was started from.
cd "$(dirname "$0")"

./realsense-depth-server

echo
read -r -p "Press Enter to close this window."
