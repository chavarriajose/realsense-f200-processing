# SPDX-License-Identifier: AGPL-3.0-or-later
# view_depth.py
#
# Quick test for the Intel RealSense F200 (Creative VF0800) on Linux.
# Reads the last depth frame from "depth.raw" (recorded with v4l2-ctl)
# and shows it as an image, so you can check that depth is working.
#
# How to use:
#   1. Record some depth frames. Replace /dev/videoN with your depth device:
#      run "v4l2-ctl --list-devices" and try the RealSense devices until one
#      accepts the 'Z16 ' format (on the first test machine it was /dev/video6).
#        v4l2-ctl -d /dev/videoN --set-fmt-video=width=640,height=480,pixelformat='Z16 ' \
#          --stream-mmap --stream-count=30 --stream-to=depth.raw
#   2. Put this file in the same folder as depth.raw
#   3. Install the libraries (only once):
#        sudo apt install python3-numpy python3-matplotlib
#   4. Run it:
#        python3 view_depth.py
#
# What to expect:
#   - "non-zero pixels" should be a big number (depth is working)
#   - closer objects and farther objects should have different colors
#   - if everything is 0, the IR laser projector is probably off

import numpy as np
import matplotlib.pyplot as plt

# Size of each depth frame (must match the size used when recording)
WIDTH = 640
HEIGHT = 480
FILENAME = "depth.raw"

# Each depth pixel is a 16-bit number (Z16 format), so we read the file
# as a long list of unsigned 16-bit integers.
data = np.fromfile(FILENAME, dtype=np.uint16)

pixels_per_frame = WIDTH * HEIGHT
frames_in_file = len(data) // pixels_per_frame
print("Frames found in file:", frames_in_file)

if frames_in_file == 0:
    print("No complete frames found. Check that depth.raw is not empty.")
    raise SystemExit

# Take the last frame in the file (the camera needs a moment to warm up,
# so the first frames can be empty) and shape it into a 2D image.
frame = data[-pixels_per_frame:].reshape(HEIGHT, WIDTH)

# Some quick numbers to see if the data makes sense.
# A value of 0 means "no depth measured" for that pixel.
valid = frame[frame > 0]
print("Min value:", frame.min())
print("Max value:", frame.max())
print("Non-zero pixels:", np.count_nonzero(frame), "of", pixels_per_frame)
if valid.size > 0:
    print("Min value (ignoring zeros):", valid.min())

# Value at the center of the image, averaged over a small 11x11 square
# (ignoring zeros) so a single noisy pixel doesn't fool us.
# Point the center of the camera at an object at a known distance
# to find out how raw values relate to real distance.
cy, cx = HEIGHT // 2, WIDTH // 2
center = frame[cy - 5:cy + 6, cx - 5:cx + 6]
center_valid = center[center > 0]
if center_valid.size > 0:
    center_value = int(np.median(center_valid))
    # Guess: librealsense v1 used 1/32 mm per unit for the F200.
    # Compare this guess with your tape measure!
    print("Center value:", center_value,
          "(about", round(center_value / 32 / 10, 1), "cm if the scale is 1/32 mm)")
else:
    print("Center value: no depth at the center of the image")

# Show the depth image. Zeros are drawn in black so they stand out.
cmap = plt.get_cmap("viridis").copy()
cmap.set_bad("black")
masked = np.ma.masked_equal(frame, 0)

plt.imshow(masked, cmap=cmap)
plt.colorbar(label="raw depth value (not millimeters yet)")
plt.title("RealSense F200 depth (black = no data)")
plt.show()
