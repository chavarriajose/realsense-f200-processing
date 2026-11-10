# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capture_linux.py

Everything that talks to the RealSense F200 camera on Linux lives in this file.
The rest of the project (the server, the tools) only uses the small interface
at the bottom of this file:

    camera = F200Camera(want_ir=True, want_color=False)
    frames = camera.read()      # frames.depth_mm, frames.ir, frames.color
    camera.close()

Why one separate file? On Linux the camera works with the normal kernel driver
(uvcvideo), so we can read it with OpenCV. On macOS or Windows that will not be
possible, and a different capture file will be needed. Keeping all camera code
here means only this file has to change for another operating system.

How the camera shows up on Linux
--------------------------------
The F200 creates several "video devices" (files like /dev/video4). Two matter:

  * the DEPTH device: gives depth and infrared (IR). It supports the
    formats 'Z16 ' (depth only), 'Y10 ' (IR only) and 'INZI' (both together).
  * the COLOR device: a normal color webcam (YUYV format, up to 1920x1080).

The numbers (/dev/video4, /dev/video6, ...) change from computer to computer,
so we never type them in. Instead we look at every video device, keep the ones
whose name contains "RealSense", and check which formats each one supports.
"""

import glob
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Depth scale
# ---------------------------------------------------------------------------
# The camera does not send millimeters. It sends a 16-bit number per pixel,
# and that number grows by 32 for every millimeter (so 1 unit = 1/32 mm).
# This value comes from Intel's original driver (librealsense v1), where the
# depth scale is computed from a calibration value called Rmax:
#     scale = Rmax / 65535  millimeters per unit,  and Rmax is about 2048
# which gives 1/32 mm per unit. We cannot read Rmax through the Linux driver,
# so we use this nominal value. If your distances look a few percent off,
# this is the number to adjust.
DEPTH_UNITS_PER_MM = 32

# A pixel with the value 0 means "the camera could not measure depth here"
# (too far, too close, a shiny or black surface, or the edge of the laser
# pattern). We keep 0 as "no depth" everywhere in this project.
NO_DEPTH = 0

# The camera's device names start with this text. We use it to find the camera.
CAMERA_NAME_HINT = "RealSense"


# ---------------------------------------------------------------------------
# Finding the camera
# ---------------------------------------------------------------------------

@dataclass
class CameraDevices:
    """The two device files we found, for example '/dev/video6'."""
    depth: str   # gives depth and infrared
    color: str   # gives the color image (can be None if not found)


def list_formats(device):
    """
    Ask the system which image formats a video device supports.

    We use the command line tool 'v4l2-ctl' (from the 'v4l-utils' package)
    because it is easy to read and already needed to test the camera.
    It prints lines like:   [1]: 'Z16 ' (16-bit Depth)
    We return the four-letter codes it finds, for example ['YUYV', 'Z16 '].
    """
    if shutil.which("v4l2-ctl") is None:
        # Without this tool we cannot tell the devices apart. Say so clearly,
        # otherwise it would look like the camera is not plugged in.
        raise RuntimeError(
            "The program 'v4l2-ctl' is missing. Please install it with:\n"
            "    sudo apt install v4l-utils"
        )
    try:
        result = subprocess.run(
            ["v4l2-ctl", "-d", device, "--list-formats"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    formats = []
    for line in result.stdout.splitlines():
        # The format code sits between the first pair of single quotes.
        if "'" in line:
            code = line.split("'")[1]
            formats.append(code)
    return formats


def find_camera():
    """
    Look through every video device and find the F200's depth and color
    devices. Returns a CameraDevices object, or raises an error with a
    friendly message if the camera is not plugged in.
    """
    depth_device = None
    color_device = None

    # Every video device has a small folder in /sys with its name inside.
    for folder in sorted(glob.glob("/sys/class/video4linux/video*")):
        with open(os.path.join(folder, "name")) as name_file:
            name = name_file.read().strip()
        if CAMERA_NAME_HINT not in name:
            continue  # some other camera, for example a laptop webcam

        device = "/dev/" + os.path.basename(folder)
        formats = list_formats(device)

        if "Z16 " in formats:
            # Only the depth device can give 16-bit depth.
            depth_device = device
        elif "YUYV" in formats and color_device is None:
            # A RealSense device with normal YUYV video is the color camera.
            color_device = device
        # Devices with no formats at all are "metadata" devices: we skip them.

    if depth_device is None:
        raise RuntimeError(
            "Could not find the RealSense F200 depth camera.\n"
            "Check that it is plugged into a USB 3.0 port, then run:\n"
            "    v4l2-ctl --list-devices\n"
            "You should see a device called 'Intel(R) RealSense(TM) 3D Camer'\n"
            "(Linux cuts the name off after 31 letters, that is normal)."
        )
    return CameraDevices(depth=depth_device, color=color_device)


# ---------------------------------------------------------------------------
# Reading frames in the background
# ---------------------------------------------------------------------------

class _BackgroundReader:
    """
    Reads frames from one video device in a background thread and always
    keeps the newest frame.

    Why a thread? Reading a frame waits until the camera delivers the next
    one. The depth and color cameras each deliver 30 frames per second, but
    not at the same moment. If we read them one after the other, each read
    would wait for the other and everything would get slower. With one thread
    per device, both keep running and we simply pick up the latest frames.
    """

    def __init__(self, capture, name):
        self.capture = capture
        self.name = name
        self.latest = None          # newest raw frame (numpy array)
        self.frame_number = 0       # counts up for every new frame
        self.error = None           # set if the camera stops working
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        failures_in_a_row = 0
        while self.running:
            ok, frame = self.capture.read()
            if not ok:
                failures_in_a_row += 1
                # A few failed reads can happen. Many in a row usually means
                # the camera was unplugged.
                if failures_in_a_row > 30:
                    self.error = f"The {self.name} camera stopped sending frames."
                    return
                time.sleep(0.01)
                continue
            failures_in_a_row = 0
            with self.lock:
                self.latest = frame
                self.frame_number += 1

    def get(self):
        """Return (frame_number, frame). frame is None until the first one arrives."""
        with self.lock:
            return self.frame_number, self.latest

    def stop(self):
        self.running = False
        self.thread.join(timeout=2)
        self.capture.release()


# ---------------------------------------------------------------------------
# The camera interface used by the rest of the project
# ---------------------------------------------------------------------------

@dataclass
class Frames:
    """
    One set of images from the camera, all as numpy arrays.

    depth_mm: height x width, uint16, distance in millimeters (0 = no depth)
    ir:       height x width, uint8, infrared brightness (None if not wanted)
    color:    480 x 640 x 3, uint8, color image in BGR order, the order
              OpenCV uses (None if not wanted or not available)
    number:   counts up by one for every new depth frame
    """
    depth_mm: np.ndarray
    ir: np.ndarray
    color: np.ndarray
    number: int


class F200Camera:
    """
    Opens the F200 and gives you depth (in millimeters), infrared and color.

    width, height: depth resolution, either 640x480 or 640x240
    fps:           depth frames per second (30 or 60 work at both sizes)
    want_ir:       also return the infrared image
    want_color:    also open the color camera (640x480)
    """

    def __init__(self, width=640, height=480, fps=30,
                 want_ir=True, want_color=False):
        self.width = width
        self.height = height
        self.want_ir = want_ir
        self.devices = find_camera()

        # --- Depth and infrared ---------------------------------------
        # We always ask for the 'INZI' format. It sends depth and infrared
        # together in one frame, so we get both for free and they always
        # match each other exactly. Each pixel is 3 bytes:
        #     2 bytes depth (little endian), then 1 byte infrared.
        # (This layout comes from Intel's librealsense v1, file src/image.cpp,
        # Apache 2.0 license.)
        depth_capture = cv2.VideoCapture(self.devices.depth, cv2.CAP_V4L2)
        depth_capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"INZI"))
        depth_capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        depth_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        depth_capture.set(cv2.CAP_PROP_FPS, fps)
        # Ask OpenCV to give us the raw bytes and not to "convert" them to a
        # color picture, which would destroy the depth values.
        depth_capture.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        if not depth_capture.isOpened():
            raise RuntimeError(
                f"Found the depth camera at {self.devices.depth} but could not "
                "open it. Is another program (or another server) using it?"
            )
        self._depth_reader = _BackgroundReader(depth_capture, "depth")

        # --- Color (optional) -------------------------------------------
        self._color_reader = None
        if want_color and self.devices.color is not None:
            color_capture = cv2.VideoCapture(self.devices.color, cv2.CAP_V4L2)
            color_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            color_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            color_capture.set(cv2.CAP_PROP_FPS, 30)
            if color_capture.isOpened():
                self._color_reader = _BackgroundReader(color_capture, "color")
            else:
                print(f"Warning: could not open the color camera at "
                      f"{self.devices.color}. Color images will be missing.")
        elif want_color:
            print("Warning: no color camera found. Color images will be missing.")

        self._last_number = -1
        self._had_good_frame = False   # becomes True after the first complete frame

    def read(self, timeout=2.0):
        """
        Wait for a new depth frame and return a Frames object.
        Raises RuntimeError if no new frame arrives within `timeout` seconds
        (for example because the camera was unplugged).
        """
        expected_bytes = self.width * self.height * 3
        deadline = time.time() + timeout
        while True:
            if self._depth_reader.error:
                raise RuntimeError(self._depth_reader.error)
            number, raw = self._depth_reader.get()
            if raw is not None and number != self._last_number:
                self._last_number = number
                if raw.size == expected_bytes:
                    break  # a complete frame: use it
                if not self._had_good_frame:
                    # The very first frame already has the wrong size: the
                    # camera did not accept the width and height we asked for.
                    raise RuntimeError(
                        f"The camera did not accept the size {self.width}x{self.height}. "
                        "The F200 depth camera supports 640x480 and 640x240."
                    )
                # Now and then a frame arrives incomplete (a USB hiccup).
                # We simply skip it and wait for the next one.
            if time.time() > deadline:
                raise RuntimeError("No new depth frame from the camera.")
            time.sleep(0.002)  # wait a tiny bit, then check again
        self._had_good_frame = True

        depth_mm, ir = self._unpack_inzi(raw)

        color = None
        if self._color_reader is not None:
            _, color = self._color_reader.get()

        return Frames(depth_mm=depth_mm,
                      ir=ir if self.want_ir else None,
                      color=color,
                      number=number)

    def _unpack_inzi(self, raw):
        """Split one INZI frame into depth (mm) and infrared."""
        # read() already checked that there are exactly 3 bytes per pixel.
        pixels = raw.reshape(self.height, self.width, 3)

        # Glue the two depth bytes together: low byte + high byte * 256.
        low = pixels[:, :, 0].astype(np.uint16)
        high = pixels[:, :, 1].astype(np.uint16)
        depth_raw = low | (high << 8)

        # Convert camera units to millimeters. Rounding (instead of cutting
        # off) keeps the error below half a millimeter. A raw 0 stays 0.
        depth_mm = np.rint(depth_raw / DEPTH_UNITS_PER_MM).astype(np.uint16)

        # The third byte is the infrared brightness. We copy it so the
        # array does not keep the whole raw frame alive in memory.
        ir = pixels[:, :, 2].copy()
        return depth_mm, ir

    def close(self):
        """Stop the background threads and release the camera."""
        self._depth_reader.stop()
        if self._color_reader is not None:
            self._color_reader.stop()


# ---------------------------------------------------------------------------
# Quick self test:  python3 server/capture_linux.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    devices = find_camera()
    print("Depth device:", devices.depth)
    print("Color device:", devices.color)

    camera = F200Camera(want_ir=True, want_color=True)
    try:
        frames = camera.read()
        valid = frames.depth_mm[frames.depth_mm != NO_DEPTH]
        print("Depth frame:", frames.depth_mm.shape, frames.depth_mm.dtype)
        print(f"Pixels with depth: {100 * valid.size / frames.depth_mm.size:.0f} %")
        if valid.size:
            print(f"Median distance: {np.median(valid):.0f} mm")
        time.sleep(0.5)  # give the color camera a moment to start
        frames = camera.read()
        print("Infrared:", None if frames.ir is None else frames.ir.shape)
        print("Color:", None if frames.color is None else frames.color.shape)
    finally:
        camera.close()
