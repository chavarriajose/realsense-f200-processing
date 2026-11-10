# SPDX-License-Identifier: AGPL-3.0-or-later
"""
processing_steps.py

Small functions that turn a depth frame (numpy array, millimeters) into the
things the server sends:

  * images:  depth8 (ready to show), depth16 (exact mm), ir, color
  * values:  nearest point, presence, biggest blob, average distance

None of these functions talk to the camera or the network. That makes them
easy to test with made-up data, and they will work the same on every
operating system.
"""

import cv2
import numpy as np

NO_DEPTH = 0


def in_range_mask(depth_mm, near_mm, far_mm):
    """
    True for every pixel whose distance is between near_mm and far_mm.
    Pixels without depth (0) are never in range.
    """
    return (depth_mm != NO_DEPTH) & (depth_mm >= near_mm) & (depth_mm <= far_mm)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def make_depth8(depth_mm, near_mm, far_mm):
    """
    A grayscale picture that is easy to show in a sketch:
      near_mm   ->  255 (white)
      far_mm    ->   20 (dark gray, so it is still different from "nothing")
      no depth, or outside the range  ->  0 (black)
    """
    position = (depth_mm.astype(np.float32) - near_mm) / float(far_mm - near_mm)
    position = np.clip(position, 0.0, 1.0)            # 0.0 = near, 1.0 = far
    gray = (255.0 - position * 235.0).astype(np.uint8)
    gray[~in_range_mask(depth_mm, near_mm, far_mm)] = 0
    return gray


# ---------------------------------------------------------------------------
# Values for OSC
# ---------------------------------------------------------------------------

def find_nearest(depth_mm, near_mm, far_mm):
    """
    The closest point inside the range: returns (x, y, mm),
    or (-1, -1, 0) if nothing is in range.

    Single depth pixels are noisy and can "jump" to a wrong value. We first
    blur the depth image with a small median filter, which removes lonely
    wrong pixels but keeps real objects. Then we look for the smallest value.
    """
    smooth = cv2.medianBlur(depth_mm, 5)
    mask = in_range_mask(smooth, near_mm, far_mm)
    if not mask.any():
        return -1, -1, 0

    # Give every pixel outside the range a huge distance, so it can never be
    # chosen as the minimum, then find where the minimum is.
    candidates = np.where(mask, smooth, np.iinfo(np.uint16).max)
    index = int(np.argmin(candidates))
    height, width = depth_mm.shape
    y, x = divmod(index, width)
    return x, y, int(smooth[y, x])


def find_presence(depth_mm, near_mm, far_mm, min_pixels):
    """1 if at least min_pixels pixels are inside the range, otherwise 0."""
    count = int(np.count_nonzero(in_range_mask(depth_mm, near_mm, far_mm)))
    return 1 if count >= min_pixels else 0


def find_average(depth_mm, near_mm, far_mm):
    """Average distance (mm) of all pixels inside the range, 0 if none."""
    mask = in_range_mask(depth_mm, near_mm, far_mm)
    if not mask.any():
        return 0
    return int(round(float(depth_mm[mask].mean())))


def find_biggest_blob(depth_mm, near_mm, far_mm, min_pixels):
    """
    The biggest connected "thing" inside the range, for example a hand.
    Returns (x, y, mm, size):
        x, y   center of the blob in pixels
        mm     average distance of the blob
        size   number of pixels in the blob
    Returns (-1, -1, 0, 0) if there is no blob with at least min_pixels pixels.
    """
    mask = in_range_mask(depth_mm, near_mm, far_mm).astype(np.uint8)

    # The depth image has many small holes and specks. "Closing" fills the
    # small holes, "opening" removes the small specks, so one object becomes
    # one blob instead of many pieces.
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Give every separate blob its own number (label) and measure each one.
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:  # label 0 is the background, so there are no blobs
        return -1, -1, 0, 0

    # Find the label with the largest area, skipping the background (0).
    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = 1 + int(np.argmax(areas))
    size = int(stats[biggest, cv2.CC_STAT_AREA])
    if size < min_pixels:
        return -1, -1, 0, 0

    x, y = centers[biggest]
    # Average distance, using only real depth pixels inside the blob
    # (the "closing" step above may have added pixels with no depth).
    blob_pixels = (labels == biggest) & (depth_mm != NO_DEPTH)
    mm = int(round(float(depth_mm[blob_pixels].mean()))) if blob_pixels.any() else 0
    return int(round(x)), int(round(y)), mm, size


def compute_values(depth_mm, near_mm, far_mm, min_pixels):
    """All OSC values in one dictionary."""
    nx, ny, nmm = find_nearest(depth_mm, near_mm, far_mm)
    bx, by, bmm, bsize = find_biggest_blob(depth_mm, near_mm, far_mm, min_pixels)
    return {
        "nearest": [nx, ny, nmm],
        "presence": [find_presence(depth_mm, near_mm, far_mm, min_pixels)],
        "blob": [bx, by, bmm, bsize],
        "average": [find_average(depth_mm, near_mm, far_mm)],
    }


# ---------------------------------------------------------------------------
# Self test with made-up data:  python3 server/processing_steps.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # A fake 640x480 scene: wall at 900 mm, and a "hand" at 400 mm.
    fake = np.full((480, 640), 900, dtype=np.uint16)
    fake[200:280, 300:380] = 400
    fake[0:10, :] = 0  # a strip with no depth
    print(compute_values(fake, 200, 1200, 2000))
    gray = make_depth8(fake, 200, 1200)
    print("depth8 at hand:", gray[240, 340], " at wall:", gray[100, 100], " no depth:", gray[0, 0])
