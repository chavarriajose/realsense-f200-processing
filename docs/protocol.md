# Protocol: what the server sends, byte by byte

You only need this page if you want to write your own client (for example in
p5.js, TouchDesigner, Python or another language). The Processing examples
already do all of this for you.

The server offers two ways to get data:

| What          | How       | Port (default) | Good for                         |
|---------------|-----------|----------------|----------------------------------|
| Images        | WebSocket | 8765           | depth pictures, exact distances  |
| Simple values | OSC (UDP) | 9000           | nearest point, presence, blob    |

The values are also available over the WebSocket, as JSON text, for
environments without OSC (like p5.js in a browser).

## Finding the server (announcements)

Once per second the server sends one UDP broadcast message to port 8766
(`discovery_port` in `config.toml`) on every network it is connected to.
The message is plain text:

```
realsense-f200 8765 9000
```

the word `realsense-f200`, then the WebSocket port, then the OSC port. To
find the server, listen on UDP port 8766 and use the address the message
came from. Allow other programs to listen on the same port at the same time
(`SO_REUSEADDR` and, where available, `SO_REUSEPORT`), so several sketches
on one computer can all hear it. Many shared networks (offices, schools, public Wi-Fi) block broadcasts; the
Processing examples then try the name `realsense.local`.

Switch the announcements off with `discovery = false` in `config.toml`.

Ports and many other settings can be changed in `server/config.toml`.

## WebSocket

Connect to `ws://<server ip>:8765`, for example `ws://192.168.1.50:8765`
(replace the address with the one the server prints when it starts).

### 1. Say what you want

Right after connecting, send one **text** message with JSON:

```json
{"streams": ["depth8", "values"]}
```

Possible names:

| Name      | What you receive                                         |
|-----------|----------------------------------------------------------|
| `depth8`  | grayscale depth picture (binary)                         |
| `depth16` | distance in millimeters for every pixel (binary)         |
| `ir`      | infrared picture (binary)                                |
| `color`   | color picture as JPEG (binary)                           |
| `values`  | nearest point, presence, blob, average (JSON text)       |

Only ask for what you need: every stream uses network bandwidth. You can send
a new request at any time to change your mind. Streams switched off in
`config.toml` are never sent (by default `ir` and `color` are off).

The server sends a new set of messages about 15 times per second
(`send_fps` in `config.toml`). If your program is slow to receive, the server
skips frames for you instead of building up a delay.

### 2. Images (binary messages)

Each image is one binary message: an 8 byte header followed by the pixels.

| Bytes | Meaning   | Values                                              |
|-------|-----------|-----------------------------------------------------|
| 0     | stream    | 1 = depth8, 2 = depth16, 3 = ir, 4 = color          |
| 1     | encoding  | 0 = raw, 1 = zlib, 2 = JPEG                         |
| 2-3   | width     | unsigned 16 bit, big endian (usually 640)           |
| 4-5   | height    | unsigned 16 bit, big endian (usually 480)           |
| 6-7   | reserved  | always 0                                            |

The rest of the message (from byte 8) is the image:

- **Encoding 1 (zlib):** first unpack the bytes with zlib ("inflate").
  Java has `java.util.zip.Inflater`, Python has `zlib.decompress`, and in
  JavaScript the `pako` library does it. After unpacking you have raw bytes.
- **depth8** (raw bytes): `width * height` bytes, one per pixel, row by row
  starting at the top left. 255 = at the near limit, 20 = at the far limit,
  0 = no depth or outside the range (`near_mm` and `far_mm` in `config.toml`).
- **depth16** (raw bytes): `width * height * 2` bytes, two per pixel,
  **big endian** (high byte first). Each value is the distance in
  **millimeters**. 0 = no depth. This stream is not limited to the range.
- **ir** (raw bytes): `width * height` bytes, infrared brightness 0 to 255.
  The image is quite dark; stretch the contrast if you want to show it.
- **color** (encoding 2): a normal JPEG file, 640 x 480. It is not aligned
  with depth (the color camera sits a few centimeters to the side).

Compression is on by default. With `compress = false` in `config.toml`, the
images arrive with encoding 0 and you can skip the unpacking.

Typical sizes per message with compression: depth8 about 40 KB, depth16
about 100 KB, ir about 170 KB, color about 30 KB.

### 3. Values (text messages)

If you asked for `values`, you also get one text message per frame:

```json
{"nearest": [312, 240, 655], "presence": [1], "blob": [320, 250, 700, 41200], "average": [870]}
```

The numbers are the same as the OSC values below.

## OSC

OSC is sent over UDP, so the server needs to know where your sketch is.

1. Your sketch listens on a UDP port of its choice (the examples use 12000).
2. It sends `/subscribe` with that port number (one integer between 1 and
   65535) to the server's OSC port, 9000. The server answers to the IP
   address the message came from. Other values are ignored, and without a
   number the server uses 12000.
3. It repeats `/subscribe` every few seconds. If the server hears nothing
   for 10 seconds (`subscription_timeout`), it stops sending. That way it
   does not keep sending to laptops that left the room.
4. Optional: send `/unsubscribe` with the same port when you stop.

Messages you receive, about 15 times per second (all integers):

| Address     | Arguments           | Meaning                                                              |
|-------------|---------------------|----------------------------------------------------------------------|
| `/nearest`  | `x y mm`            | closest point inside the range. `-1 -1 0` if nothing is in range.    |
| `/presence` | `0` or `1`          | 1 if at least `min_pixels` pixels are inside the range               |
| `/blob`     | `x y mm size`       | center, average distance and pixel count of the biggest object. `-1 -1 0 0` if none. |
| `/average`  | `mm`                | average distance of everything inside the range, 0 if nothing        |

`x` and `y` are pixel positions in the depth image (0 to 639 and 0 to 479
at the default size), with (0, 0) at the top left. Use `map()` to convert
them to your sketch's size.

The range is set by `near_mm` and `far_mm` in `config.toml`
(default 200 to 1200 mm).
