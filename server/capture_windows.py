# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capture_windows.py

Everything that talks to the RealSense F200 camera on Windows lives in this
file. It offers exactly the same small interface as capture_linux.py and
capture_macos.py, so the server does not need to know which computer it runs
on:

    camera = F200Camera(want_ir=True, want_color=False)
    frames = camera.read()      # frames.depth_mm, frames.ir, frames.color
    camera.close()

How does Windows see the camera?
--------------------------------
When you plug in the F200, Windows loads its own standard webcam driver for
it (no Intel software needed). Windows then shows two cameras:

  * "Intel(R) RealSense(TM) 3D Camera (Front F200) RGB"    the color camera
  * "Intel(R) RealSense(TM) 3D Camera (Front F200) Depth"  depth and infrared

Normal webcam programs (and OpenCV) only understand the usual picture formats,
so they show the depth camera as a strange grey image. But Windows' video
system, called "Media Foundation", does list the camera's special depth
formats, and it hands their data over untouched if we ask for them by name.
So we talk to Media Foundation directly.

Media Foundation is made of "COM objects", Windows' way of offering services
to programs. Python can call them with its built-in "ctypes" module, so no
extra package is needed. The price is some plumbing code at the top of this
file. You do not need to understand it to use the camera.

docs/windows/camera-notes.md explains everything we found out on the way.
"""

import ctypes
import threading
import time
import uuid
from ctypes import (HRESULT, POINTER, WINFUNCTYPE, byref, c_uint32, c_uint64,
                    c_ulong, c_void_p, c_wchar_p)
from dataclasses import dataclass

import cv2
import numpy as np


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
# How to recognize the camera
# ---------------------------------------------------------------------------
# Windows gives every camera a long internal name (a "symbolic link"), which
# contains the USB ID numbers of the device: Intel is 8086 and the F200 is
# 0a66. The "mi_" part says which part ("interface") of the camera it is:
# mi_00 is the color camera, mi_02 is depth and infrared. We look for these
# instead of the camera's display name, because they never change.
F200_USB_ID = "vid_8086&pid_0a66"
COLOR_INTERFACE = "mi_00"
DEPTH_INTERFACE = "mi_02"

# Image formats are named by four letters. 'INZI' is depth and infrared in
# one frame, so they always match each other exactly. 'YUY2' is the normal
# webcam format the color camera uses.
DEPTH_FORMAT = "INZI"
COLOR_FORMAT = "YUY2"
COLOR_WIDTH, COLOR_HEIGHT = 640, 480
COLOR_FPS = 30

# How many times we try to start the camera before giving up.
START_ATTEMPTS = 4

# How long (in seconds) we wait for Windows to open the camera.
START_TIMEOUT = 15.0

# How long (in seconds) we wait for the camera to deliver its first image.
FIRST_FRAME_TIMEOUT = 5.0


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
# Plumbing: calling Windows' Media Foundation from Python
# ---------------------------------------------------------------------------
# You can skip this part. It turns the C-style Windows functions into a few
# small Python helpers.

class _GUID(ctypes.Structure):
    """
    A GUID is a 16-byte ID number that Windows uses to name things: settings,
    services and also image formats. We write them as text like
    "f7e34c9a-42e8-4714-b74b-cb29d72c35e5", as Microsoft's documentation does.
    """
    _fields_ = [("data", ctypes.c_ubyte * 16)]

    @staticmethod
    def from_text(text):
        guid = _GUID()
        ctypes.memmove(guid.data, uuid.UUID(text).bytes_le, 16)
        return guid

    def to_uuid(self):
        return uuid.UUID(bytes_le=bytes(self.data))


# The GUIDs we need, with the names Microsoft gives them.
_MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = _GUID.from_text("c60ac5fe-252a-478f-a0ef-bc8fa5f7cad3")
_MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID = _GUID.from_text("8ac3587a-4ae7-42d8-99e0-0a6013eef90f")
_MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME = _GUID.from_text("60d0e559-52f8-4fa2-bbce-acdb34a8ec01")
_MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK = _GUID.from_text("58f0aad8-22bf-4f8a-bb3d-d2c4978c6e2f")
_MF_READWRITE_DISABLE_CONVERTERS = _GUID.from_text("98d5b065-1374-4847-8d5d-31520fee7156")
_MF_MT_SUBTYPE = _GUID.from_text("f7e34c9a-42e8-4714-b74b-cb29d72c35e5")
_MF_MT_FRAME_SIZE = _GUID.from_text("1652c33d-d6b2-4012-b834-72030849a37d")
_MF_MT_FRAME_RATE = _GUID.from_text("c459a2e8-3d2c-4e44-b132-fee5156c7bb0")
_IID_IMFMediaSource = _GUID.from_text("279a808d-aec7-40c8-9c6b-a6b492c78a66")

# Other numbers from Microsoft's documentation.
_MF_VERSION = 0x00020070                     # "the Media Foundation of Windows 7 or newer"
_COINIT_MULTITHREADED = 0x0
_MF_SOURCE_READER_FIRST_VIDEO_STREAM = 0xFFFFFFFC
_MF_SOURCE_READERF_ERROR = 0x1
_MF_SOURCE_READERF_ENDOFSTREAM = 0x2

# Every COM object is a table of functions. Each function has a fixed
# position ("slot") in that table. These are the slots we use, taken from
# Microsoft's header files (mfobjects.h, mfidl.h, mfreadwrite.h).
_SLOT_RELEASE = 2                  # every object
_SLOT_GET_UINT64 = 8               # IMFAttributes and everything built on it
_SLOT_GET_GUID = 10
_SLOT_GET_ALLOCATED_STRING = 13
_SLOT_SET_UINT32 = 21
_SLOT_SET_GUID = 24
_SLOT_ACTIVATE_OBJECT = 33         # IMFActivate
_SLOT_SHUTDOWN_OBJECT = 34
_SLOT_GET_NATIVE_MEDIA_TYPE = 5    # IMFSourceReader
_SLOT_SET_CURRENT_MEDIA_TYPE = 7
_SLOT_READ_SAMPLE = 9
_SLOT_CONVERT_TO_CONTIGUOUS_BUFFER = 41   # IMFSample
_SLOT_LOCK = 3                     # IMFMediaBuffer
_SLOT_UNLOCK = 4


def _com_call(com_object, slot, *arguments, types=()):
    """
    Call function number `slot` of a COM object. `types` lists the ctypes
    types of the arguments. If Windows reports an error, ctypes raises an
    OSError that carries Windows' error number.
    """
    function_table = ctypes.cast(com_object, POINTER(POINTER(c_void_p)))[0]
    function = WINFUNCTYPE(HRESULT, c_void_p, *types)(function_table[slot])
    return function(com_object, *arguments)


def _release(com_object):
    """Tell a COM object we do not need it any more (it frees itself)."""
    if com_object:
        function_table = ctypes.cast(com_object, POINTER(POINTER(c_void_p)))[0]
        WINFUNCTYPE(c_ulong, c_void_p)(function_table[_SLOT_RELEASE])(com_object)


def _get_text(attributes, key):
    """Read a text setting (like a camera's name) from a COM object."""
    text = c_wchar_p()
    length = c_uint32()
    _com_call(attributes, _SLOT_GET_ALLOCATED_STRING, byref(key), byref(text), byref(length),
              types=(POINTER(_GUID), POINTER(c_wchar_p), POINTER(c_uint32)))
    value = text.value
    ctypes.windll.ole32.CoTaskMemFree(text)   # Windows made the copy, we free it
    return value


def _check(result, what):
    """
    Many Windows functions return a result number instead of raising an
    error: 0 means "OK", anything else is an error number. Turn that into
    an OSError, like _com_call does.
    """
    if result != 0:
        raise OSError(None, what, None, result)


def _new_attributes():
    """Make an empty "attributes" object (a small list of settings)."""
    attributes = c_void_p()
    _check(ctypes.windll.mfplat.MFCreateAttributes(byref(attributes), 1),
           "Could not prepare the camera settings")
    return attributes


def _get_uint64(attributes, key):
    value = c_uint64()
    _com_call(attributes, _SLOT_GET_UINT64, byref(key), byref(value),
              types=(POINTER(_GUID), POINTER(c_uint64)))
    return value.value


def _four_letters(media_type):
    """
    The four-letter name of an image format, like "YUY2" or "INZI".
    Media Foundation names formats by GUIDs whose first 4 bytes are the four
    letters, so we read those back.
    """
    subtype = _GUID()
    _com_call(media_type, _SLOT_GET_GUID, byref(_MF_MT_SUBTYPE), byref(subtype),
              types=(POINTER(_GUID), POINTER(_GUID)))
    return bytes(subtype.data[:4]).decode("latin-1")


# Windows error numbers we know how to explain in plain words.
_E_ACCESSDENIED = 0x80070005
_MF_E_HW_MFT_FAILED_START_STREAMING = 0xC00D3704
_MF_E_VIDEO_RECORDING_DEVICE_INVALIDATED = 0xC00D3E85
_MF_E_VIDEO_RECORDING_DEVICE_PREEMPTED = 0xC00D3E86


def _explain(problem):
    """Turn a Windows error into a message a person can act on."""
    code = (getattr(problem, "winerror", None) or 0) & 0xFFFFFFFF
    if code == _E_ACCESSDENIED:
        return ("Windows does not allow this program to use the camera.\n"
                "Open Settings > Privacy & security > Camera and switch on\n"
                "'Camera access' and 'Let desktop apps access your camera'.")
    if code in (_MF_E_HW_MFT_FAILED_START_STREAMING,
                _MF_E_VIDEO_RECORDING_DEVICE_PREEMPTED):
        return ("The camera is busy: another program is using it (for example\n"
                "the Camera app, a video call, or another depth server).\n"
                "Close that program first.")
    if code == _MF_E_VIDEO_RECORDING_DEVICE_INVALIDATED:
        return "The camera was unplugged or switched off."
    return f"Windows reported a camera error ({problem})."


class _CannotWork(RuntimeError):
    """A problem that trying again will not fix (camera missing, bad size)."""


# ---------------------------------------------------------------------------
# One image stream (depth or color), read in its own background thread
# ---------------------------------------------------------------------------

class _MfStream:
    """
    Reads one camera stream with Media Foundation in a background thread and
    always keeps the newest frame, so read() never has to wait long.

    Why a thread of our own? Windows' camera objects like to be used from the
    thread that created them. The server calls the camera from changing
    helper threads, so we keep all Media Foundation work inside this one
    thread, and only hand finished frames (plain bytes) to the outside.
    """

    def __init__(self, interface, four_letters, width, height, fps, name):
        self.interface = interface
        self.four_letters = four_letters
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name

        self.camera_name = None   # filled in by the thread
        self.error = None         # set by the thread if something goes wrong
        self.cannot_work = False  # True if trying again would not help
        self._frame = (0, None)   # (frame number, bytes)
        self._lock = threading.Lock()
        self._started = threading.Event()
        self._stop = threading.Event()

        self._thread = threading.Thread(target=self._run, name=f"F200 {name}", daemon=True)
        self._thread.start()

        # Wait until the thread has opened the camera (or failed to). Opening
        # takes well under a second; if Windows does not answer at all, we
        # give up instead of waiting forever.
        if not self._started.wait(timeout=START_TIMEOUT):
            self._stop.set()
            raise RuntimeError("The camera did not answer.")
        if self.error:
            self._thread.join(timeout=2)
            kind = _CannotWork if self.cannot_work else RuntimeError
            raise kind(self.error)

    def get(self):
        """Return (frame number, bytes) of the newest frame."""
        with self._lock:
            return self._frame

    def stop(self):
        self._stop.set()
        # ReadSample returns at the next frame (1/30 s), then the thread ends.
        self._thread.join(timeout=3)

    # --- everything below runs inside the background thread -----------------

    def _run(self):
        ole32 = ctypes.windll.ole32
        mfplat = ctypes.windll.mfplat
        ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        mfplat.MFStartup(_MF_VERSION, 0)
        activate = None
        # _open() stores the camera objects here as soon as it creates them,
        # so the "finally" part below can always release them, even when
        # something fails halfway.
        self._source = c_void_p()
        self._reader = c_void_p()
        try:
            activate = self._find_camera()
            self._open(activate)
            self._started.set()   # the camera works, let __init__ continue
            self._read_frames(self._reader)
        except _CannotWork as problem:
            self.error = str(problem)
            self.cannot_work = True
        except OSError as problem:
            self.error = _explain(problem)
        except RuntimeError as problem:   # our own messages, for example "unplugged"
            self.error = str(problem)
        except Exception as problem:   # anything unexpected: report it, do not hang
            self.error = f"Unexpected camera problem: {problem!r}"
        finally:
            # Clean up in reverse order. Releasing the reader also stops the
            # camera; ShutdownObject lets Windows give it to other programs.
            _release(self._reader)
            _release(self._source)
            if activate:
                try:
                    _com_call(activate, _SLOT_SHUTDOWN_OBJECT)
                except OSError:
                    pass
                _release(activate)
            mfplat.MFShutdown()
            ole32.CoUninitialize()
            self._started.set()   # in case we failed before opening

    def _find_camera(self):
        """Ask Windows for all cameras and pick the right part of the F200."""
        mf = ctypes.windll.mf

        # "We are looking for video capture devices."
        search = _new_attributes()
        devices = POINTER(c_void_p)()
        count = c_uint32()
        try:
            _com_call(search, _SLOT_SET_GUID, byref(_MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE),
                      byref(_MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID),
                      types=(POINTER(_GUID), POINTER(_GUID)))
            _check(mf.MFEnumDeviceSources(search, byref(devices), byref(count)),
                   "Could not list the cameras")
        finally:
            _release(search)

        # Look at every camera. We keep the one we want and release all
        # others, also if asking one of them fails.
        found = None
        try:
            for index in range(count.value):
                device = devices[index]
                try:
                    if found is None:
                        link = _get_text(
                            device, _MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK).lower()
                        if F200_USB_ID in link and f"&{self.interface}" in link:
                            self.camera_name = _get_text(
                                device, _MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME)
                            found = device
                            continue   # keep this one, do not release it
                except Exception:
                    pass   # a camera that does not answer properly: skip it
                _release(device)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(devices)

        if found is None:
            raise _CannotWork(
                "Could not find the RealSense F200 camera.\n"
                "Check that it is plugged in (a USB 3.0 port, hub or adapter).\n"
                "In Device Manager > Cameras it is called\n"
                "'Intel(R) RealSense(TM) 3D Camera (Front F200) Depth' (and 'RGB').")
        return found

    def _open(self, activate):
        """
        Open the camera and choose our format, size and speed. The camera
        objects go into self._source and self._reader, which _run() releases.
        """
        _com_call(activate, _SLOT_ACTIVATE_OBJECT, byref(_IID_IMFMediaSource),
                  byref(self._source), types=(POINTER(_GUID), POINTER(c_void_p)))

        # A "source reader" hands us the camera's images one by one. We tell
        # it not to convert anything: we want the camera's bytes untouched.
        settings = _new_attributes()
        try:
            _com_call(settings, _SLOT_SET_UINT32, byref(_MF_READWRITE_DISABLE_CONVERTERS), 1,
                      types=(POINTER(_GUID), c_uint32))
            _check(ctypes.windll.mfreadwrite.MFCreateSourceReaderFromMediaSource(
                       self._source, settings, byref(self._reader)),
                   "Could not open the camera")
        finally:
            _release(settings)
        reader = self._reader

        # The camera offers a "menu" of formats. Go through it and pick ours.
        offered = []
        index = 0
        while True:
            media_type = c_void_p()
            try:
                _com_call(reader, _SLOT_GET_NATIVE_MEDIA_TYPE,
                          _MF_SOURCE_READER_FIRST_VIDEO_STREAM, index, byref(media_type),
                          types=(c_uint32, c_uint32, POINTER(c_void_p)))
            except OSError:
                break   # end of the menu
            index += 1
            try:
                try:
                    letters = _four_letters(media_type)
                    size = _get_uint64(media_type, _MF_MT_FRAME_SIZE)
                    rate = _get_uint64(media_type, _MF_MT_FRAME_RATE)
                except OSError:
                    continue   # an entry without size or speed: not ours
                # Both numbers come packed as two halves of one 64-bit number.
                width, height = size >> 32, size & 0xFFFFFFFF
                fps = (rate >> 32) / max(1, rate & 0xFFFFFFFF)
                if letters == self.four_letters and (width, height) == (self.width, self.height):
                    offered.append(round(fps))
                    if round(fps) == self.fps:
                        _com_call(reader, _SLOT_SET_CURRENT_MEDIA_TYPE,
                                  _MF_SOURCE_READER_FIRST_VIDEO_STREAM, None, media_type,
                                  types=(c_uint32, c_void_p, c_void_p))
                        return   # found it
            finally:
                _release(media_type)

        if offered:
            raise _CannotWork(
                f"The camera does not offer {self.fps} frames per second at "
                f"{self.width}x{self.height}. It offers: {sorted(set(offered))}")
        raise _CannotWork(
            f"The camera does not offer {self.name} as {self.four_letters} at "
            f"{self.width}x{self.height}.")

    def _read_frames(self, reader):
        """Keep reading frames until stop() is called or the camera fails."""
        number = 0
        while not self._stop.is_set():
            stream_index = c_uint32()
            flags = c_uint32()
            timestamp = ctypes.c_int64()
            sample = c_void_p()
            # Waits until the camera delivers the next frame.
            _com_call(reader, _SLOT_READ_SAMPLE,
                      _MF_SOURCE_READER_FIRST_VIDEO_STREAM, 0,
                      byref(stream_index), byref(flags), byref(timestamp), byref(sample),
                      types=(c_uint32, c_uint32, POINTER(c_uint32), POINTER(c_uint32),
                             POINTER(ctypes.c_int64), POINTER(c_void_p)))
            if flags.value & (_MF_SOURCE_READERF_ERROR | _MF_SOURCE_READERF_ENDOFSTREAM):
                raise RuntimeError("The camera stopped sending images (unplugged?).")
            if not sample:
                continue   # no image this time, only a "still alive" signal
            try:
                data = self._copy_bytes(sample)
            finally:
                _release(sample)
            number += 1
            with self._lock:
                self._frame = (number, data)

    @staticmethod
    def _copy_bytes(sample):
        """Copy the image bytes out of a Media Foundation sample."""
        buffer = c_void_p()
        _com_call(sample, _SLOT_CONVERT_TO_CONTIGUOUS_BUFFER, byref(buffer),
                  types=(POINTER(c_void_p),))
        try:
            pointer = c_void_p()
            max_length = c_uint32()
            length = c_uint32()
            _com_call(buffer, _SLOT_LOCK, byref(pointer), byref(max_length), byref(length),
                      types=(POINTER(c_void_p), POINTER(c_uint32), POINTER(c_uint32)))
            try:
                return ctypes.string_at(pointer, length.value)
            finally:
                _com_call(buffer, _SLOT_UNLOCK)
        finally:
            _release(buffer)


# ---------------------------------------------------------------------------
# The camera
# ---------------------------------------------------------------------------

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
        self._last_number = 0

        # Now and then a camera does not start on the first try (for example
        # right after another program let go of it). Waiting a little and
        # trying again fixes that.
        for attempt in range(1, START_ATTEMPTS + 1):
            try:
                self._start_streams(width, height, fps, want_color)
                self._wait_for_first_frame()
                break   # the camera works
            except _CannotWork:
                self.close()   # trying again would not help
                raise
            except RuntimeError:
                self.close()
                if attempt == START_ATTEMPTS:
                    raise
                time.sleep(2)

        self.devices = CameraDevices(
            depth=self._depth_stream.camera_name,
            color=self._color_stream.camera_name if self._color_stream else None)

    def _start_streams(self, width, height, fps, want_color):
        # Each INZI pixel is 3 bytes: 2 bytes depth, then 1 byte infrared.
        self._depth_stream = _MfStream(DEPTH_INTERFACE, DEPTH_FORMAT,
                                       width, height, fps, "depth")
        if want_color:
            try:
                self._color_stream = _MfStream(COLOR_INTERFACE, COLOR_FORMAT,
                                               COLOR_WIDTH, COLOR_HEIGHT, COLOR_FPS, "color")
            except RuntimeError as problem:
                # Depth is what matters most, so we carry on without color.
                print(f"Warning: color images will be missing. {problem}")

    def _wait_for_first_frame(self):
        """Raise RuntimeError if no depth frame arrives in time."""
        deadline = time.time() + FIRST_FRAME_TIMEOUT
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
            if color_raw is not None and len(color_raw) == COLOR_WIDTH * COLOR_HEIGHT * 2:
                yuy2 = np.frombuffer(color_raw, np.uint8).reshape(COLOR_HEIGHT, COLOR_WIDTH, 2)
                color = cv2.cvtColor(yuy2, cv2.COLOR_YUV2BGR_YUY2)

        return Frames(depth_mm=depth_mm,
                      ir=ir if self.want_ir else None,
                      color=color,
                      number=number)

    def _unpack_inzi(self, raw):
        """
        Split one INZI frame into depth (mm) and infrared.
        (The same steps as in capture_macos.py: the camera sends the same
        bytes, only the way they reach us is different.)
        """
        expected = self.width * self.height * 3
        if len(raw) != expected:
            raise RuntimeError(f"Depth frame has {len(raw)} bytes, expected {expected}.")
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

    def close(self):
        """Stop everything and let other programs use the camera again."""
        for stream in (self._depth_stream, self._color_stream):
            if stream is not None:
                stream.stop()
        self._depth_stream = None
        self._color_stream = None


# ---------------------------------------------------------------------------
# Quick self test:  .venv\Scripts\python server\capture_windows.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        camera = F200Camera(want_ir=True, want_color=True)
    except RuntimeError as problem:
        # Show only our friendly message, not a long Python error report.
        print(problem)
        raise SystemExit(1)
    try:
        print("Depth:", camera.devices.depth, " Color:", camera.devices.color)
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
