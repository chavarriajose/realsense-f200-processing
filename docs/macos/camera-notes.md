# Camera notes: the F200 on macOS

What we found out about using the RealSense F200 directly on a Mac, and why
the macOS capture code works the way it does. Tested on an Apple Silicon Mac
with macOS 26, the camera connected through a USB 3.0 hub (most Macs have no
USB-A port, so a hub or adapter is normal and works fine).

## How macOS sees the camera

macOS has a built-in webcam driver (a helper program called `UVCAssistant`).
It takes the camera as soon as it is plugged in. You can see this with:

```bash
ioreg -p IOService -l -w0 -r -n "Intel(R) RealSense(TM) 3D Camera (Front F200)" | grep -E '\+-o'
```

The camera has five USB "interfaces" (think of them as separate doors):

| Interface | What it is                     | Who holds it on macOS |
|-----------|--------------------------------|-----------------------|
| 0         | color camera, controls         | `UVCAssistant`        |
| 1         | color camera, image stream     | `UVCAssistant`        |
| 2         | depth camera, controls         | `UVCAssistant`        |
| 3         | depth camera, image stream     | `UVCAssistant`        |
| 4         | Intel's own command channel    | nobody (free to use)  |

Both image streams use **bulk** USB transfers (not isochronous ones), which
makes them simple to read from a normal program.

## What the depth camera can send

Read from the camera's own USB descriptors:

| Format | Bytes per pixel | What it contains |
|--------|-----------------|------------------|
| `YUY2` | 2 | depth (16 bit), disguised as a normal webcam format, 30 fps only |
| `INVZ` | 2 | depth (16 bit) |
| `INZI` | 3 | depth (16 bit) and infrared (8 bit) together, **what we use** |
| `INVR` | 2 | 16-bit infrared |
| `INRI` | 3 | another depth + infrared combination |
| `INVI` | 1 | 8-bit infrared, up to 300 fps |
| `RELI` | 1 | infrared with the laser pattern switched off and on (640x480 only) |

Sizes: 640x480 and 640x240. `INZI` runs at 2 to 60 fps (110 fps at 640x240).

The color camera sends normal `YUY2` video from 320x180 up to 1920x1080
(60 fps up to 960x540, 30 fps above).

## Two ways to read the camera

### 1. Through macOS itself (no password needed): depth only

macOS lists **one** webcam for this device, called "Intel(R) RealSense(TM)
3D Camera (Front F200) Depth". It only understands the `YUY2` format, and
on the depth camera `YUY2` actually carries 16-bit depth. macOS hands the
bytes over unchanged, so the depth values are correct.

- No infrared (the infrared formats are not standard, macOS ignores them).
- No color: macOS only shows one webcam per USB device, so the color camera
  is hidden.
- About one start in six gets no frames; stopping and starting again fixes it.

Quick test with ffmpeg (`brew install ffmpeg`). We ask for `uyvy422`
because asking for `yuyv422` hangs; `uyvy422` gives the same bytes with
each pair swapped, so we read them as big endian 16-bit numbers:

```bash
ffmpeg -f avfoundation -framerate 30 -video_size 640x480 -pixel_format uyvy422 \
  -i "Intel(R) RealSense(TM) 3D Camera (Front F200) Depth" -frames:v 30 -f rawvideo depth.bin
```

### 2. Directly over USB with libusb (admin password needed): everything

A program can take the camera away from macOS with libusb
(`libusb_detach_kernel_driver`, which on macOS takes the whole device).
**macOS only allows this for programs running as root**, which is why the
server asks for the admin password. Without root, libusb answers
`LIBUSB_ERROR_ACCESS`. When the program lets go of the camera, macOS takes
it back automatically, and the normal webcam works again.

Once we hold the camera, we talk standard UVC (the USB video standard):

1. **Probe**: send a 34-byte "probe" request to the stream interface with
   the format number, frame size number and frame interval we want
   (`SET_CUR`, request `0x01`, value `0x0100`).
2. Read back what the camera agreed to (`GET_CUR`). It tells us the frame
   size in bytes and the biggest transfer it will send.
3. **Commit**: send the same bytes as "commit" (value `0x0200`). The camera
   starts streaming.
4. Read the bulk endpoint (`0x82` for depth, `0x83` for color). Each
   transfer starts with a small header: byte 0 is the header length, byte 1
   has flags. Flag bit 0 flips with every new frame, flag bit 1 marks the end
   of a frame. Everything after the header is image data.

Tested results (speaker at about 50 cm, camera on the table):

- `INZI` 640x480: complete frames of 921600 bytes, depth and infrared look
  right. Pixel layout: 2 bytes depth (little endian) then 1 byte infrared,
  the same as on Linux. Speaker reads about 490 mm with 1/32 mm per unit.
- Color `YUY2` 640x480: complete frames of 614400 bytes, a normal photo.

Python packages: `libusb1` (a thin wrapper around the libusb library) and
`numpy`. The libusb library itself comes from Homebrew (`brew install libusb`)
or is bundled inside the app.

## Things to avoid (learned the hard way)

- **Do not reset the camera with `libusb_reset_device`.** On macOS the F200
  dropped off the USB bus and only came back after unplugging it.
- If a capture hangs, stop it with a timeout and start again instead of
  forcing it. The capture code waits a few seconds for the first frame and
  then reopens the camera.

## Intel's command channel (interface 4)

Interface 4 accepts Intel's own commands (laser power, calibration data and
more, see `src/ivcam-private.cpp` in librealsense v1). It is free on macOS,
so a normal program can use it without the password. We do not use it yet.
