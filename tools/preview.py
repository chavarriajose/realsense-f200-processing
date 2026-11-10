# SPDX-License-Identifier: AGPL-3.0-or-later
r"""
preview.py

A live preview window for the RealSense F200, to run on the computer the
camera is plugged into (Linux or Mac). Use it to check that the camera works
and to aim it, before starting the server.

How to run it (from the main project folder):

    on Linux:   python3 tools/preview.py
    on a Mac:   sudo .venv/bin/python tools/preview.py
    on Windows: .venv\Scripts\python tools\preview.py

(On a Mac the camera can only be used with administrator rights, see
docs/macos/camera-notes.md. The server must not be running at the same time.)

What you see: three pictures side by side.
    left:   depth (near = bright, far = dark, black = no depth)
    middle: infrared
    right:  color

Keys:
    s   save a screenshot as preview.png
    q   quit (or press Escape)

Extra option, used by the automatic tests:
    python3 tools/preview.py --snapshot preview.png
takes one screenshot after a short warm up, saves it and quits, without
opening a window.
"""

import os
import sys
import time

import cv2
import numpy as np

# The capture code lives in the "server" folder next to this one.
# These two lines let Python find it.
PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_FOLDER, "server"))

from capture import F200Camera, NO_DEPTH  # noqa: E402

# Distances shown in the depth picture, in millimeters.
NEAR_MM = 200
FAR_MM = 1200


def depth_to_picture(depth_mm):
    """
    Turn depth in millimeters into a grayscale picture:
    NEAR_MM becomes white, FAR_MM becomes dark gray, no depth stays black.
    """
    # Where is each pixel between near (0.0) and far (1.0)?
    position = (depth_mm.astype(np.float32) - NEAR_MM) / (FAR_MM - NEAR_MM)
    position = np.clip(position, 0.0, 1.0)
    # Near is bright (255), far is darker (but not black, so it stays visible).
    gray = (255 - position * 215).astype(np.uint8)
    # Pixels without depth, or outside the range, are black.
    outside = (depth_mm == NO_DEPTH) | (depth_mm < NEAR_MM) | (depth_mm > FAR_MM)
    gray[outside] = 0
    return gray


def make_preview(frames):
    """Put depth, infrared and color side by side in one picture."""
    height, width = frames.depth_mm.shape
    depth = cv2.cvtColor(depth_to_picture(frames.depth_mm), cv2.COLOR_GRAY2BGR)

    # Infrared is quite dark, so we stretch its brightness to use the full
    # range from black to white. This only changes how it looks.
    ir = cv2.normalize(frames.ir, None, 0, 255, cv2.NORM_MINMAX)
    ir = cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)

    if frames.color is not None:
        color = cv2.resize(frames.color, (width, height))
    else:
        color = np.zeros_like(depth)  # black if there is no color image

    picture = np.hstack([depth, ir, color])

    # Write the distance at the center of the image on top of the picture.
    center = frames.depth_mm[height // 2 - 5:height // 2 + 5,
                             width // 2 - 5:width // 2 + 5]
    valid = center[center != NO_DEPTH]
    text = f"center: {np.median(valid):.0f} mm" if valid.size else "center: no depth"
    cv2.putText(picture, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 200, 255), 2)
    return picture


def main():
    snapshot_path = None
    if "--snapshot" in sys.argv:
        position = sys.argv.index("--snapshot")
        if position + 1 >= len(sys.argv):
            print("Please give a file name after --snapshot, for example:")
            print("    python3 tools/preview.py --snapshot preview.png")
            return
        snapshot_path = sys.argv[position + 1]

    try:
        camera = F200Camera(want_ir=True, want_color=True)
    except RuntimeError as problem:
        # Show only our friendly message, not a long Python error report.
        print(problem)
        sys.exit(1)
    print("Camera open. Depth:", camera.devices.depth, " Color:", camera.devices.color)

    try:
        if snapshot_path:
            # Let the camera run for one second so exposure settles.
            end = time.time() + 1.0
            while time.time() < end:
                frames = camera.read()
            cv2.imwrite(snapshot_path, make_preview(camera.read()))
            print("Saved", snapshot_path)
            return

        print("Press 's' to save a screenshot, 'q' to quit.")
        while True:
            picture = make_preview(camera.read())
            cv2.imshow("RealSense F200 preview", picture)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                cv2.imwrite("preview.png", picture)
                print("Saved preview.png")
            if key in (ord("q"), 27):  # 27 is the Escape key
                break
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
