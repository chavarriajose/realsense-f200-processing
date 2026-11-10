# Processing examples

Five example sketches for Processing 4 (Java mode), from simple to more
advanced. Each one shows one idea.

| Sketch                   | What it shows                                              | Needs          |
|--------------------------|------------------------------------------------------------|----------------|
| `example01_show_depth`   | the depth image (near = bright, far = dark)                | nothing extra  |
| `example02_nearest_point`| a circle on the closest thing, with its distance           | nothing extra  |
| `example03_threshold`    | only what is between two distances (arrow keys change them) | nothing extra |
| `example04_point_cloud`  | the depth as 3D dots, drag the mouse to turn it            | nothing extra  |
| `example05_osc_values`   | nearest point, presence, blob and average, no images       | oscP5 library  |

A step by step guide for your first sketch (Mac, Windows and Linux) is in
[docs/first-sketch.md](../docs/first-sketch.md).

These examples are under the [MIT license](LICENSE): use them freely as a
starting point for your own sketches and artworks.

## Before you run a sketch

1. The depth server must be running on the computer the camera is plugged
   into, and your computer must be on the same network. That can be a
   shared Linux computer, or your own Mac or Windows PC (see
   `docs/macos/setup.md` or `docs/windows/setup.md`; then the sketch and the
   server are on the same computer).
2. Open the sketch in Processing (double click the `.pde` file with the same
   name as the folder, for example `example01_show_depth.pde`).
3. At the top of the sketch you find:

   ```java
   String SERVER = "auto";
   ```

   "auto" finds the server on the network by itself. If the sketch keeps
   saying `Looking for the depth server`, your network blocks this. Then
   write one of the addresses shown in the server's window instead, for
   example `"realsense.local"` or `"192.168.1.50"` (only an example: your
   server has its own address).

4. Press Run. After a second or two you should see the camera image. Until
   then the window says `Looking for the depth server (auto) ...`.

## Libraries

Examples 01 to 04 need no library. They use two extra tabs:

- `DepthClient` connects to the server, with the WebSocket client that is
  built into Java, and turns what arrives into images and numbers.
- `ServerFinder` turns `"auto"` into the server's real address.

Every sketch has its own copy of these tabs (all copies are the same), so
each folder works on its own and you can copy a folder to start your own
project.

Example 05 has a second tab called `TestHelper`. It is only used by the
project's automatic tests; you can ignore it.

Example 05 needs **oscP5**. Install it once:

1. In Processing, choose **Sketch > Import Library > Manage Libraries...**
2. Type `oscP5` in the search field.
3. Select **oscP5** and click **Install**.

## Using DepthClient in your own sketch

Copy `DepthClient.pde` and `ServerFinder.pde` from any example into your
sketch folder, then:

```java
String SERVER = "auto";
DepthClient camera;

void setup() {
  size(640, 480);
  // Ask for the streams you need: "depth8", "depth16", "ir", "color", "values"
  camera = new DepthClient(this, SERVER, "depth8", "depth16");
}

void draw() {
  if (camera.depthImage != null) {
    image(camera.depthImage, 0, 0);              // the depth picture
  }
  int mm = camera.getDistance(320, 240);         // distance at the center, in mm
}
```

What you can use:

| Name                      | What it is                                                    | Stream     |
|---------------------------|---------------------------------------------------------------|------------|
| `camera.depthImage`       | grayscale depth picture (`PImage`)                            | `depth8`   |
| `camera.depthMM`          | distance in mm for every pixel (`int[]`, 0 = no depth)        | `depth16`  |
| `camera.getDistance(x, y)`| distance in mm at one pixel                                   | `depth16`  |
| `camera.irImage`          | infrared picture (`PImage`)                                   | `ir`       |
| `camera.colorImage`       | color picture (`PImage`)                                      | `color`    |
| `camera.values`           | nearest, presence, blob, average (`JSONObject`)               | `values`   |
| `camera.depthWidth`, `camera.depthHeight` | size of the depth image (640 x 480)          |            |
| `camera.isConnected()`    | `true` while connected to the server                          |            |

Everything is `null` until the first frame arrives, so check for `null`
before you draw (all examples show how). The `ir` and `color` streams are
switched off on the server by default; ask the person running the server
to switch them on in `config.toml` if you need them.

## For developers: testing the examples automatically

On Linux, `tools/linux/run_sketch_headless.sh` runs a sketch without a screen and
saves a screenshot. On a Mac, `tools/macos/run_sketch_macos.sh` does the same (the
sketch window opens for a few seconds), and on Windows
`tools/windows/run_sketch_windows.ps1`. `tools/README.md` explains how to
set them up.
