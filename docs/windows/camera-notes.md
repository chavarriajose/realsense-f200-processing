# Camera notes: the F200 on Windows

What we found out about the RealSense F200 on Windows, and why the server
reads it the way it does. Useful if you want to change the capture code
(`server/capture_windows.py`) or understand an error message. You do not
need any of this to use the camera.

Tested on Windows 11 (64-bit) with the camera on a USB 3.0 hub, without any
Intel software installed.

## What Windows does when you plug in the camera

Windows recognizes the F200 by itself and loads its own drivers. Nothing
needs to be installed. In Device Manager you see:

| Where in Device Manager | Name | Driver | What it is |
|---|---|---|---|
| Cameras | `Intel(R) RealSense(TM) 3D Camera (Front F200) RGB` | `usbvideo` (Windows' webcam driver) | the color camera (USB interface 0) |
| Cameras | `Intel(R) RealSense(TM) 3D Camera (Front F200) Depth` | `usbvideo` | depth and infrared (USB interfaces 2 and 3) |
| Universal Serial Bus devices | `Intel(R) RealSense(TM) 3D Camera (Front F200)` | `WinUSB` | the camera's special controls (interface 4), not used by this project |
| Sound, video and game controllers | `Creative VF0800` | Windows' audio driver | microphones, ignored |

Windows gives every camera a long internal name, for example
`\\?\usb#vid_8086&pid_0a66&mi_02#...`. The part `vid_8086&pid_0a66` is the
F200's USB ID and `mi_02` means "interface 2" (depth). The server looks for
these two parts, so it does not depend on the order of the cameras or on the
language of Windows.

## What the depth camera offers

Windows' video system, **Media Foundation**, lists these formats for the
"Depth" camera (the four letters are the start of the format's GUID):

| Format | Sizes | Frames per second | Bytes per pixel | Content |
|---|---|---|---|---|
| `INZI` | 640x480, 640x240 | 2, 5, 15, 30, 60 (110 at 640x240) | 3 | depth (16 bit) and infrared (8 bit), **what we use** |
| `INVZ` | 640x480, 640x240 | same | 2 | depth only (16 bit) |
| `INVR` | 640x480, 640x240 | same | 2 | 16-bit infrared |
| `INRI` | 640x480, 640x240 | same | | depth and infrared, another layout |
| `INVI` | 640x480, 640x240 | 30, 60, 120, 240, 300 | 1 | 8-bit infrared, very fast |
| `RELI` | 640x480 | 60, 120, 200, 400 | | infrared with the laser switching on and off |
| `YUY2` | 640x480, 640x240 | 30 | 2 | what normal webcam programs see: a grey picture |

The color camera offers `YUY2` from 320x180 up to 1920x1080 (60 fps up to
960x540, 30 fps above). The server uses 640x480 at 30 fps, like on Linux and
macOS.

## How Python reads it

We tried, from simple to more work:

1. **OpenCV** (`cv2.VideoCapture` with the Media Foundation or DirectShow
   backend). It opens both F200 cameras, but only ever delivers `YUY2`: asking
   for `INZI` or `Z16` is silently ignored. So it cannot give us depth.
2. **Media Foundation directly, from Python's built-in `ctypes` module.**
   This works. We list the cameras (`MFEnumDeviceSources`), open the F200's
   depth camera, pick the `INZI` format from its menu, switch off all format
   converters (`MF_READWRITE_DISABLE_CONVERTERS`) and read the frames with a
   "source reader". The bytes arrive exactly as the camera sends them: 921600
   bytes per 640x480 frame, the same layout as on macOS. **This is what
   `server/capture_windows.py` does.**

Route 2 needs no extra Python package, no driver change and no administrator
rights. The fallback that was planned in case it failed (replacing the
driver with Zadig and talking USB like on macOS) was not needed.

Each camera stream is read in its own background thread, which creates, uses
and releases all Media Foundation objects itself. The server calls the
camera from changing helper threads, and keeping Windows' camera objects in
one thread avoids a whole class of hard to find problems.

## Checks we made

- **Depth values:** `INZI` depth and `INVZ` depth (depth only) were captured
  one after the other and compared pixel by pixel: they agree within 0.14 %
  (median). The speaker cone of the test scene reads about 548 mm with both.
- **Scale:** the same `DEPTH_UNITS_PER_MM = 32` as on Linux and macOS.
- **Speed:** 30 depth frames per second, with color running at the same time.
- **Orientation:** depth, infrared and color look the same way round as on
  Linux and macOS (not mirrored, not upside down).
- **Camera busy:** Windows lets only one program read the depth camera at a
  time. A second program gets the error `MF_E_HW_MFT_FAILED_START_STREAMING`
  (or `..._DEVICE_PREEMPTED`), which the server turns into "The camera is
  busy: another program is using it". The first program keeps running.
- **Camera privacy:** if Settings > Privacy & security > Camera blocks
  desktop apps, Windows answers "access denied" and the server says which
  switches to turn on.

## Things to avoid

- Do not use the "Depth" camera in normal webcam programs and expect depth:
  they show the `YUY2` grey picture, not distances.
- Windows Hello (face sign-in) can use this camera. If it is set up, it may
  hold the camera while the sign-in screen is shown. The server then reports
  "camera busy" and tries again.
