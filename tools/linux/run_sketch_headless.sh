#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# run_sketch_headless.sh
#
# Runs one Processing example on this Linux computer without a screen and
# saves a screenshot. The project uses it to test the examples automatically.
# You do not need it to use the examples: simply press Run in Processing.
#
# Usage (from the main project folder, with the server running):
#   tools/linux/run_sketch_headless.sh processing/example01_show_depth example01.png
#
# It needs:
#   - Processing 4, by default in .tools/Processing (change with PROCESSING=...)
#   - a sketchbook folder with the oscP5 library in it, by default in
#     .tools/home/sketchbook/libraries (change with PROCESSING_HOME=...)
#   - xvfb-run (sudo apt install xvfb), a "pretend screen" for the window

set -e

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
PROCESSING="${PROCESSING:-$PROJECT/.tools/Processing/bin/Processing}"
PROCESSING_HOME="${PROCESSING_HOME:-$PROJECT/.tools/home}"
SERVER="${SERVER:-127.0.0.1}"

SKETCH="$(cd "$1" && pwd)"
SCREENSHOT="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"

# Remove an old screenshot first, so we never report an old picture as new.
rm -f "$SCREENSHOT"

# Java cannot handle a home folder whose path contains spaces, so we point
# to the sketchbook through a temporary link with a simple path.
LINK_FOLDER="$(mktemp -d)"
ln -s "$PROCESSING_HOME" "$LINK_FOLDER/home"
trap 'rm -rf "$LINK_FOLDER"' EXIT

HOME="$LINK_FOLDER/home" JAVA_TOOL_OPTIONS="-Duser.home=$LINK_FOLDER/home" \
  timeout 90 xvfb-run -a -s "-screen 0 1280x1024x24" \
  "$PROCESSING" cli --sketch="$SKETCH" --run \
  "--server=$SERVER" "--screenshot=$SCREENSHOT" 2>&1 | grep -v "Picked up JAVA_TOOL_OPTIONS" || true

if [ -f "$SCREENSHOT" ]; then
  echo "OK: $SCREENSHOT"
else
  echo "FAILED: no screenshot saved. Is the server running? See the messages above."
  exit 1
fi
