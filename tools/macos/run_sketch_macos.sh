#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# run_sketch_macos.sh
#
# Runs one Processing example on this Mac and saves a screenshot. The
# project uses it to test the examples automatically. You do not need it
# to use the examples: simply press Run in Processing.
#
# Usage (from the main project folder, with the server running):
#   tools/macos/run_sketch_macos.sh processing/example01_show_depth example01.png
#
# The sketch window opens for a few seconds and closes by itself.
# By default the sketch finds the server by itself (SERVER = "auto").
# To use a fixed address instead:   SERVER=127.0.0.1 tools/macos/run_sketch_macos.sh ...
#
# It needs Processing 4 in /Applications (change with PROCESSING=...) and, for
# example 05, the oscP5 library installed from Processing's Contribution
# Manager.

set -e

if [ $# -ne 2 ]; then
  echo "Usage: tools/macos/run_sketch_macos.sh <sketch folder> <screenshot.png>"
  exit 1
fi

PROCESSING="${PROCESSING:-/Applications/Processing.app/Contents/MacOS/Processing}"

SKETCH="$(cd "$1" && pwd)"
SCREENSHOT="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"

# Only pass --server when an address was given, so "auto" is tested otherwise.
SERVER_OPTION=()
if [ -n "$SERVER" ]; then
  SERVER_OPTION=("--server=$SERVER")
fi

# Remove an old screenshot first, so we never report an old picture as new.
rm -f "$SCREENSHOT"

# macOS has no "timeout" command, so we let perl stop the sketch after
# 90 seconds if something hangs. The grep hides two harmless warnings that
# Processing prints on every Mac (about a Linux-only Java package and about
# pixelDensity on Retina screens).
perl -e 'alarm 90; exec @ARGV' \
  "$PROCESSING" cli --sketch="$SKETCH" --run \
  "${SERVER_OPTION[@]}" "--screenshot=$SCREENSHOT" 2>&1 \
  | grep -v -e "sun.awt.X11" -e "pixelDensity" || true

if [ -f "$SCREENSHOT" ]; then
  echo "OK: $SCREENSHOT"
else
  echo "FAILED: no screenshot saved. Is the server running? See the messages above."
  exit 1
fi
