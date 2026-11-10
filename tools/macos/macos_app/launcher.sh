#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# launcher.sh
#
# This is what runs when you double click "RealSense Depth Server.app".
# (The build script copies it into the app as Contents/MacOS/launcher.)
# It opens start-server.command in a Terminal window, so you can see what
# the server says and type your password there.

APP="$(cd "$(dirname "$0")/../.." && pwd)"
RESOURCES="$APP/Contents/Resources"

# When you download the app, macOS marks every file inside it as "from the
# internet" (the "quarantine" mark). You allowed the app itself once in
# System Settings > Privacy & Security, otherwise this script would not be
# running. But macOS would still block the helper files inside the app (the
# Terminal script and the server program) one by one. Since you already
# said yes to the app, we remove that mark from the files inside this app,
# and only inside this app.
xattr -dr com.apple.quarantine "$APP" 2>/dev/null

# If the mark is still there, the app is probably still in the Downloads
# folder: macOS then runs it from a hidden read-only copy, where nothing can
# be changed. Moving it to Applications fixes that. (In rare cases another
# user account installed the app, and only that account can change it.)
if xattr -p com.apple.quarantine "$RESOURCES/start-server.command" >/dev/null 2>&1; then
  osascript -e 'display dialog "Please move RealSense Depth Server into your Applications folder (drag it there in Finder), then open it again from there. If it is already there, ask whoever installed it to open it once." buttons {"OK"} default button "OK" with title "RealSense Depth Server"' >/dev/null
  exit 1
fi

open -a Terminal "$RESOURCES/start-server.command"
