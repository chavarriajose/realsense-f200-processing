# Camera notes: the F200 on Linux

Technical notes about how the Intel RealSense F200 (Creative VF0800) behaves
with the standard Linux driver. You do not need this page to use the project;
it is here for anyone who wants to understand or improve the capture code.

## Devices

`v4l2-ctl --list-devices` shows one entry called
`Intel(R) RealSense(TM) 3D Camer` (the kernel cuts names at 31 characters)
with four video devices. The numbers
change between computers, so the code finds them by name and by format:

| Device role | How we recognize it            | Formats                              |
|-------------|--------------------------------|--------------------------------------|
| Depth / IR  | supports `'Z16 '`              | `YUYV`, `'Z16 '`, `INZI`, `'Y10 '`   |
| Color       | supports `YUYV` but not `Z16`  | `YUYV`, from 320x180 up to 1920x1080 |
| Metadata    | lists no formats at all        | (ignored)                            |

Note that some format codes end with a space: `'Z16 '` and `'Y10 '`.

## Depth formats and frame rates

Measured on the test machine with `server/capture_linux.py`:

| Format | Size    | Frame rates offered          | Measured with our code |
|--------|---------|------------------------------|------------------------|
| `INZI` | 640x480 | 60, 30, 15, 5, 2             | 30 fps: 30, 60 fps: about 57 |
| `INZI` | 640x240 | 110, 60, 30, 15, 5, 2        | 60 fps: 60             |
| `Z16 ` | same as `INZI` |                       |                        |
| `Y10 ` | 640x480, 640x240 | up to 300           | (not used)             |

`INZI` packs depth and infrared together: 3 bytes per pixel, first 2 bytes
are depth (little endian), the last byte is infrared brightness. This layout
is documented in Intel's librealsense v1 (`src/image.cpp`,
`unpack_z16_y8_from_f200_inzi`). Because it gives both images in one frame,
the project always uses `INZI`.

## Reading frames from Python

OpenCV (`python3-opencv` from apt) with the V4L2 backend works. The trick is
to switch off OpenCV's color conversion so the bytes arrive untouched:

```python
cap = cv2.VideoCapture("/dev/videoN", cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"INZI"))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
```

`cap.read()` then returns a `uint8` array with exactly
`width * height * 3` bytes. No extra library or compiled module is needed.
(With `'Z16 '` it returns `width * height * 2` bytes that can be viewed as `uint16`.)

## Depth scale

librealsense v1 computes the scale as `Rmax / 65535` millimeters per unit,
where `Rmax` is a calibration value stored in the camera. It can only be read
with a special USB command that the Linux driver does not offer. The nominal
value is 1/32 mm per unit, which the code uses (`DEPTH_UNITS_PER_MM = 32`).

Measured: a wall roughly 90 cm away (estimated, not measured with a tape)
reads a median of about 960 to 980 mm with this scale (raw values about
30700 to 31300, depending on the run). The raw `Z16` stream and the `INZI`
unpacking agree within 0.5 %. If your distances look a few percent off when
you check them with a tape measure (from the front glass of the camera),
`DEPTH_UNITS_PER_MM` is the number to adjust, and please tell us what you
measured.

## Range and missing depth

- Pixels with value 0 have no depth.
- Looking at a wall at 90 cm, only about 35 % of the pixels have depth. The
  laser pattern gets weak at the edges and beyond about 1 m. A second
  surface 15 cm further away (about 1050 mm) returns almost no depth.
  The F200 is best between about 20 cm and 80 cm, which matches its design
  as a camera for faces and hands in front of a laptop.

## Camera controls

`v4l2-ctl -d <depth device> --list-ctrls` lists **no controls**. The F200's
special settings are "extension unit" controls that the Linux driver does not
publish. librealsense v1 (`src/f200.cpp`) lists them with their ranges:

| Setting              | Range  | Default | What it does                                   |
|----------------------|--------|---------|------------------------------------------------|
| Laser power          | 0..16  | 16      | brightness of the infrared laser pattern       |
| Accuracy             | 1..3   | 2       | number of patterns used per depth frame        |
| Motion range         | 0..100 | 0       | trades exposure time against motion blur       |
| Filter option        | 0..7   | 5       | amount of smoothing / hole filling in the camera |
| Confidence threshold | 0..15  | 6       | how sure the camera must be before it reports depth |

These could be set from userspace through the `UVCIOC_CTRL_QUERY` ioctl
without any driver, but this is not done yet. The defaults (laser at full
power) work.
