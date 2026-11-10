#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# install_launcher.sh
#
# Adds a "RealSense Depth Server" icon to your desktop and to the app menu
# (press the Super key and type "depth"). Double clicking it opens a window
# that runs the server and shows the address for sketches.
#
# Run it once, from the main project folder:
#     tools/linux/install_launcher.sh
#
# Run it again if you move the project to another folder.
# To remove the icon: delete "realsense-depth-server.desktop" from your
# Desktop folder and from ~/.local/share/applications.

set -e

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
NAME="realsense-depth-server.desktop"
APPS_FOLDER="$HOME/.local/share/applications"
DESKTOP_FOLDER="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"

chmod +x "$PROJECT/start-server.sh"

# A ".desktop" file is how Linux describes an app icon: its name, its
# picture, and what to run. "Terminal=true" opens it in a terminal window.
# The quotes around the path keep it working if a folder name has spaces.
mkdir -p "$APPS_FOLDER"
cat > "$APPS_FOLDER/$NAME" <<EOF
[Desktop Entry]
Type=Application
Name=RealSense Depth Server
Comment=Start the depth camera server for Processing sketches
Exec="$PROJECT/start-server.sh"
Icon=camera-video
Terminal=true
Categories=Education;
EOF
chmod +x "$APPS_FOLDER/$NAME"
echo "Added to the app menu: $APPS_FOLDER/$NAME"

# Also put a copy on the desktop, and mark it as trusted so Ubuntu lets you
# start it with a double click.
if [ -d "$DESKTOP_FOLDER" ]; then
  cp "$APPS_FOLDER/$NAME" "$DESKTOP_FOLDER/$NAME"
  chmod +x "$DESKTOP_FOLDER/$NAME"
  gio set "$DESKTOP_FOLDER/$NAME" metadata::trusted true 2>/dev/null || true
  echo "Added to the desktop: $DESKTOP_FOLDER/$NAME"
fi

echo
echo "Done. Double click \"RealSense Depth Server\" on the desktop to start the server."
echo "(If Ubuntu still asks, right click the icon and choose \"Allow Launching\".)"
