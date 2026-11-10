# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capture_macos.py

Everything that talks to the RealSense F200 camera on macOS lives in this
file. It offers exactly the same small interface as capture_linux.py, so the
server does not need to know which computer it runs on:

    camera = F200Camera(want_ir=True, want_color=False)
    frames = camera.read()      # frames.depth_mm, frames.ir, frames.color
    camera.close()

Why is macOS different from Linux?
----------------------------------
On Linux the normal video driver understands the F200's depth formats, so we
can read it like a webcam. macOS also has a webcam driver, but it ignores the
special depth formats and hides the color camera. So on macOS we skip the
driver and talk to the camera ourselves over USB, using the libusb library.

The camera speaks "UVC", the standard language of USB webcams. Talking UVC
ourselves takes three steps for each image stream:

  1. "probe":  tell the camera which format, size and speed we want,
  2. "commit": confirm it, and the camera starts sending,
  3. read the image data as it arrives, and glue the pieces into frames.

One catch: macOS only lets a program take a camera away from its own driver
when the program runs as an administrator ("root"). That is why the server
must be started with sudo on a Mac, and why the Mac app asks for your
password. When we let go of the camera, macOS takes it back by itself.

docs/macos/camera-notes.md explains everything we found out on the way.
"""

import fcntl
import os
import struct
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
import usb1


# ---------------------------------------------------------------------------
# Depth scale (the same as on Linux, see capture_linux.py for the story)
# ---------------------------------------------------------------------------
# The camera sends a 16-bit number per pixel that grows by 32 for every
# millimeter (1 unit = 1/32 mm). This value comes from Intel's original
# driver, librealsense v1. If your distances look a few percent off, this is
# the number to adjust.
DEPTH_UNITS_PER_MM = 32

# A pixel with the value 0 means "the camera could not measure depth here".
NO_DEPTH = 0


# ---------------------------------------------------------------------------
# How to recognize the camera on the USB bus
# ---------------------------------------------------------------------------
# Every USB device has two ID numbers: one for the maker and one for the
# product. Intel is 8086 and the F200 is 0a66 (you can see them in
# System Information > USB). We look for these instead of a name, because
# they are always the same.
INTEL_VENDOR_ID = 0x8086
F200_PRODUCT_ID = 0x0a66

# The camera has several "interfaces" (think of them as separate doors).
# Interface 1 sends color images, interface 3 sends depth and infrared.
COLOR_STREAM_INTERFACE = 1
DEPTH_STREAM_INTERFACE = 3

# Image formats are named by four letters. 'INZI' is depth and infrared in
# one frame, so they always match each other exactly. 'YUY2' is the normal
# webcam format the color camera uses.
DEPTH_FORMAT = b"INZI"
COLOR_FORMAT = b"YUY2"
COLOR_WIDTH, COLOR_HEIGHT = 640, 480

# UVC request numbers (from the USB Video Class standard).
UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
UVC_PROBE_CONTROL = 0x0100    # "this is what I would like"
UVC_COMMIT_CONTROL = 0x0200   # "OK, start sending"
# Request types: "class request to an interface", out (to the camera) or in.
REQUEST_TO_CAMERA = 0x21
REQUEST_FROM_CAMERA = 0xA1

# How long (in milliseconds) we wait for one piece of image data before we
# check again whether we should stop.
USB_READ_TIMEOUT_MS = 500

# How many times we try to start the camera before giving up.
START_ATTEMPTS = 4

# While a program uses the camera, it holds a lock on this small file, so a
# second program knows the camera is taken (see F200Camera below).
LOCK_FILE_PATH = "/tmp/realsense-f200.lock"


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


@dataclass
class CameraDevices:
    """Where the images come from. Only used to print a helpful message."""
    depth: str
    color: str


# ---------------------------------------------------------------------------
# Reading the camera's "menu" of formats
# ---------------------------------------------------------------------------

@dataclass
class StreamFormat:
    """The numbers the camera needs to hear to send one format and size."""
    format_index: int     # which format, as the camera numbers them (1, 2, ...)
    frame_index: int      # which size, inside that format
    endpoint: int         # the USB "pipe" the images come out of
    frame_rates: list     # frames per second the camera offers at this size


def find_stream_format(device, interface_number, fourcc, width, height):
    """
    Look through the camera's description of itself (its "descriptors") and
    find the numbers for one format and size. This way we never hardcode
    numbers that could differ between camera firmware versions.
    """
    for configuration in device:
        for interface in configuration:
            for setting in interface:
                if setting.getNumber() != interface_number:
                    continue
                endpoints = [endpoint.getAddress() for endpoint in setting]
                format_index = None
                # The descriptors are a list of small byte blocks. Byte 2 of
                # each block says what kind of block it is.
                for block in setting.getExtra():
                    block = bytes(block)
                    kind = block[2]
                    if kind in (0x04, 0x10):
                        # A FORMAT block (0x04 = uncompressed, 0x10 = "frame
                        # based"). Bytes 5 to 8 start with the four letters.
                        if block[5:9] == fourcc:
                            format_index = block[3]
                        elif format_index is not None:
                            break  # we passed our format, stop looking
                    elif kind in (0x05, 0x11) and format_index is not None:
                        # A FRAME block: one image size of the format above.
                        block_width, block_height = struct.unpack_from("<HH", block, 5)
                        if (block_width, block_height) == (width, height):
                            # The list of frame intervals (time between
                            # frames, in units of 100 nanoseconds) sits at a
                            # different place in the two kinds of blocks.
                            count_at = 25 if kind == 0x05 else 21
                            count = block[count_at]
                            intervals = struct.unpack_from(f"<{count}I", block, 26)
                            rates = [round(10_000_000 / interval) for interval in intervals]
                            return StreamFormat(format_index, block[3], endpoints[0], rates)
    return None


# ---------------------------------------------------------------------------
# One running image stream, read in the background
# ---------------------------------------------------------------------------

class _UvcStream:
    """
    Starts one image stream (depth or color) and reads it in a background
    thread, always keeping the newest complete frame.

    Why a thread? Reading waits until the camera delivers data. The depth and
    color cameras each send 30 frames per second, but not at the same moment.
    With one thread per stream, both keep running and we simply pick up the
    latest frames.
    """

    def __init__(self, handle, interface_number, stream_format, fps, frame_bytes, name):
        self.handle = handle
        self.interface_number = interface_number
        self.endpoint = stream_format.endpoint
        self.frame_bytes = frame_bytes
        self.name = name
        self.latest = None          # newest complete frame (bytes)
        self.frame_number = 0       # counts up for every new frame
        self.error = None           # set if the camera stops working
        self.lock = threading.Lock()
        self.running = True

        # Take this interface away from macOS's own driver. "Auto detach"
        # means libusb does it for us now, and gives it back when we let go.
        handle.setAutoDetachKernelDriver(True)
        handle.claimInterface(interface_number)

        # Step 1, probe: ask for our format, size and speed. We first read
        # the camera's current settings (34 bytes) and only change the parts
        # we care about, so all other fields keep sensible values.
        settings = bytearray(self._get_settings())
        frame_interval = round(10_000_000 / fps)   # in units of 100 ns
        # Field layout from the UVC standard: hint (2 bytes), format index
        # (1), frame index (1), frame interval (4).
        struct.pack_into("<HBBI", settings, 0, 1, stream_format.format_index,
                         stream_format.frame_index, frame_interval)
        handle.controlWrite(REQUEST_TO_CAMERA, UVC_SET_CUR, UVC_PROBE_CONTROL,
                            interface_number, bytes(settings), timeout=1000)

        # The camera answers with what it agreed to. Bytes 22 to 25 say the
        # biggest piece of data it will send at once.
        agreed = self._get_settings()
        self.max_transfer = struct.unpack_from("<I", agreed, 22)[0]

        # Step 2, commit: confirm the agreed settings. Streaming starts now.
        handle.controlWrite(REQUEST_TO_CAMERA, UVC_SET_CUR, UVC_COMMIT_CONTROL,
                            interface_number, agreed, timeout=1000)

        # Step 3 happens in the background thread.
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _get_settings(self):
        return bytes(self.handle.controlRead(REQUEST_FROM_CAMERA, UVC_GET_CUR,
                                             UVC_PROBE_CONTROL, self.interface_number,
                                             34, timeout=1000))

    def _loop(self):
        """
        Read pieces of image data and glue them into frames.

        Every piece starts with a small header:
            byte 0: how long the header is
            byte 1: flags. Bit 0 flips between 0 and 1 with every new frame,
                    bit 1 means "this piece ends the frame",
                    bit 6 means "something went wrong with this frame".
        Everything after the header is image data.
        """
        frame = bytearray()
        frame_toggle = None
        frame_has_error = False
        quiet_reads = 0
        while self.running:
            try:
                piece = self.handle.bulkRead(self.endpoint, self.max_transfer,
                                             timeout=USB_READ_TIMEOUT_MS)
            except usb1.USBErrorTimeout:
                # No data for half a second. A few of these can happen;
                # many in a row means the camera stopped (or was unplugged).
                quiet_reads += 1
                if quiet_reads > 6:
                    self.error = f"The {self.name} camera stopped sending images."
                    return
                continue
            except usb1.USBError as problem:
                if self.running:
                    self.error = f"Lost the {self.name} camera: {problem}"
                return
            quiet_reads = 0
            if len(piece) < 2:
                continue

            header_length, flags = piece[0], piece[1]
            toggle = flags & 0x01
            if frame_toggle is not None and toggle != frame_toggle:
                # A new frame started before the old one said "end": the old
                # one is incomplete. Throw it away and start fresh.
                frame = bytearray()
                frame_has_error = False
            frame_toggle = toggle
            if flags & 0x40:
                frame_has_error = True
            frame += piece[header_length:]

            if flags & 0x02:  # end of frame
                if len(frame) == self.frame_bytes and not frame_has_error:
                    with self.lock:
                        self.latest = bytes(frame)
                        self.frame_number += 1
                # Incomplete frames (a USB hiccup) are simply skipped.
                frame = bytearray()
                frame_toggle = None
                frame_has_error = False

    def get(self):
        """Return (frame_number, frame). frame is None until the first one arrives."""
        with self.lock:
            return self.frame_number, self.latest

    def stop(self):
        """Stop the thread, tell the camera to stop, and let go of the interface."""
        self.running = False
        self.thread.join(timeout=2)
        try:
            # For bulk streams the UVC standard says: clearing the "halt"
            # state of the endpoint tells the camera to stop sending.
            self.handle.clearHalt(self.endpoint)
        except usb1.USBError:
            pass  # the camera may already be gone (unplugged)
        try:
            self.handle.releaseInterface(self.interface_number)
        except usb1.USBError:
            pass


class _CannotWork(RuntimeError):
    """A problem that trying again will not fix (camera missing, bad size)."""


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
        self._depth_stream = None
        self._color_stream = None

        if os.geteuid() != 0:
            raise RuntimeError(
                "On a Mac the camera can only be used with administrator rights\n"
                "(macOS only lets administrators take a camera away from its own\n"
                "driver). Start the program with sudo in front, for example:\n"
                "    sudo .venv/bin/python server/depth_server.py\n"
                "or use the RealSense Depth Server app, which asks for your password."
            )

        # Only one program may use the camera at a time. On Linux the driver
        # makes sure of that, but on a Mac, a second program running as
        # administrator could simply take the camera away from the first,
        # and the two would keep stealing it from each other. So we hold a
        # small "lock file" while we use the camera. The system releases the
        # lock by itself when our program ends, even after a crash.
        #
        # Safety: we run as administrator and /tmp can be written by anyone.
        # O_NOFOLLOW refuses to follow a "shortcut" (symbolic link) someone
        # could have placed there, and we never empty the file, so a prank
        # link can not make us damage another file.
        try:
            self._lock_file = os.open(LOCK_FILE_PATH,
                                      os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o644)
        except OSError as problem:
            raise _CannotWork(
                f"Could not use the lock file {LOCK_FILE_PATH} ({problem}).\n"
                "If it is a link to another file, delete it and try again.")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._lock_file)
            self._lock_file = None
            raise RuntimeError(
                "The camera is busy: another depth server (or the preview tool)\n"
                "is already using it on this Mac. Close that one first.")

        self.devices = CameraDevices(
            depth=f"USB interface {DEPTH_STREAM_INTERFACE}",
            color=f"USB interface {COLOR_STREAM_INTERFACE}" if want_color else None)
        self._usb = None
        self._handle = None
        self._last_number = 0

        # Right after another program let go of the camera, macOS needs a
        # few seconds to take it back, and starting the camera in that moment
        # fails. Now and then the camera also simply does not start sending.
        # Both are fixed by letting go, waiting a little and trying again.
        for attempt in range(1, START_ATTEMPTS + 1):
            try:
                self._start_streams(width, height, fps, want_color)
                self._wait_for_first_frame()
                return   # the camera works
            except _CannotWork:
                self.close()   # trying again would not help
                raise
            except RuntimeError:
                self._stop_streams()
                if attempt == START_ATTEMPTS:
                    self.close()
                    raise
                time.sleep(2)

    def _start_streams(self, width, height, fps, want_color):
        """Find the camera on the USB bus, then start depth (and color)."""
        self._usb = usb1.USBContext()
        try:
            self._handle = self._usb.openByVendorIDAndProductID(
                INTEL_VENDOR_ID, F200_PRODUCT_ID)
        except usb1.USBError as problem:
            raise RuntimeError(f"Found the F200 but could not open it: {problem}")
        if self._handle is None:
            raise _CannotWork(
                "Could not find the RealSense F200 camera.\n"
                "Check that it is plugged in (a USB 3.0 hub or adapter is fine).\n"
                "In System Information > USB it is called\n"
                "'Intel(R) RealSense(TM) 3D Camera (Front F200)'."
            )
        device = self._handle.getDevice()

        # --- Depth and infrared -------------------------------------------
        depth_format = find_stream_format(device, DEPTH_STREAM_INTERFACE,
                                          DEPTH_FORMAT, width, height)
        if depth_format is None:
            raise _CannotWork(
                f"The camera does not offer depth at {width}x{height}. "
                "The F200 depth camera supports 640x480 and 640x240.")
        if fps not in depth_format.frame_rates:
            raise _CannotWork(
                f"The camera does not offer {fps} frames per second at "
                f"{width}x{height}. It offers: {depth_format.frame_rates}")
        try:
            # Each INZI pixel is 3 bytes: 2 bytes depth, then 1 byte infrared.
            self._depth_stream = _UvcStream(self._handle, DEPTH_STREAM_INTERFACE,
                                            depth_format, fps, width * height * 3,
                                            "depth")

            # --- Color (optional) -------------------------------------------
            if want_color:
                color_format = find_stream_format(device, COLOR_STREAM_INTERFACE,
                                                  COLOR_FORMAT, COLOR_WIDTH, COLOR_HEIGHT)
                if color_format is None:
                    print("Warning: the color camera does not offer 640x480. "
                          "Color images will be missing.")
                else:
                    # YUY2 uses 2 bytes per pixel.
                    self._color_stream = _UvcStream(
                        self._handle, COLOR_STREAM_INTERFACE, color_format, 30,
                        COLOR_WIDTH * COLOR_HEIGHT * 2, "color")
        except usb1.USBError as problem:
            # Turn USB errors into the kind of error the server knows how to
            # handle (it waits and tries again).
            raise RuntimeError(f"Could not start the camera: {problem}")

    def _wait_for_first_frame(self, timeout=3.0):
        """Raise RuntimeError if no complete depth frame arrives in time."""
        deadline = time.time() + timeout
        while self._depth_stream.get()[1] is None:
            if self._depth_stream.error:
                raise RuntimeError(self._depth_stream.error)
            if time.time() > deadline:
                raise RuntimeError("The camera did not start sending images.")
            time.sleep(0.01)

    def read(self, timeout=3.0):
        """
        Wait for a new depth frame and return a Frames object.
        Raises RuntimeError if no new frame arrives within `timeout` seconds
        (for example because the camera was unplugged). The server then
        closes the camera and opens it again.
        """
        # Keep our own reference: if close() is called from another thread
        # while we wait (for example on Ctrl+C), this stays usable.
        depth_stream = self._depth_stream
        if depth_stream is None:
            raise RuntimeError("The camera is closed.")
        deadline = time.time() + timeout
        while True:
            if depth_stream.error:
                raise RuntimeError(depth_stream.error)
            number, raw = depth_stream.get()
            if raw is not None and number != self._last_number:
                self._last_number = number
                break
            if time.time() > deadline:
                raise RuntimeError("No new depth frame from the camera.")
            time.sleep(0.002)  # wait a tiny bit, then check again

        depth_mm, ir = self._unpack_inzi(raw)

        color = None
        color_stream = self._color_stream
        if color_stream is not None:
            _, color_raw = color_stream.get()
            if color_raw is not None:
                yuy2 = np.frombuffer(color_raw, np.uint8).reshape(COLOR_HEIGHT, COLOR_WIDTH, 2)
                color = cv2.cvtColor(yuy2, cv2.COLOR_YUV2BGR_YUY2)

        return Frames(depth_mm=depth_mm,
                      ir=ir if self.want_ir else None,
                      color=color,
                      number=number)

    def _unpack_inzi(self, raw):
        """Split one INZI frame into depth (mm) and infrared."""
        pixels = np.frombuffer(raw, np.uint8).reshape(self.height, self.width, 3)

        # Glue the two depth bytes together: low byte + high byte * 256.
        low = pixels[:, :, 0].astype(np.uint16)
        high = pixels[:, :, 1].astype(np.uint16)
        depth_raw = low | (high << 8)

        # Convert camera units to millimeters. Rounding (instead of cutting
        # off) keeps the error below half a millimeter. A raw 0 stays 0.
        depth_mm = np.rint(depth_raw / DEPTH_UNITS_PER_MM).astype(np.uint16)

        # The third byte is the infrared brightness.
        ir = pixels[:, :, 2].copy()
        return depth_mm, ir

    def _stop_streams(self):
        """Stop the streams and give the camera back to macOS."""
        for stream in (self._depth_stream, self._color_stream):
            if stream is not None:
                stream.stop()
        self._depth_stream = None
        self._color_stream = None
        if self._handle is not None:
            self._handle.close()   # macOS takes the camera back now
            self._handle = None
        if self._usb is not None:
            self._usb.close()
            self._usb = None

    def close(self):
        """Stop everything and let other programs use the camera again."""
        self._stop_streams()
        if self._lock_file is not None:
            os.close(self._lock_file)   # closing the file releases the lock
            self._lock_file = None


# ---------------------------------------------------------------------------
# Quick self test:  sudo .venv/bin/python server/capture_macos.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        camera = F200Camera(want_ir=True, want_color=True)
    except RuntimeError as problem:
        # Show only our friendly message, not a long Python error report.
        print(problem)
        raise SystemExit(1)
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

        # Measure the frame rate over three seconds.
        start, count = time.time(), 0
        while time.time() - start < 3:
            camera.read()
            count += 1
        print(f"Depth frames per second: {count / (time.time() - start):.1f}")
    finally:
        camera.close()
