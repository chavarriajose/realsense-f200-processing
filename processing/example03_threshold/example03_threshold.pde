// SPDX-License-Identifier: MIT
// example03_threshold
//
// Shows only what is between two distances, like an invisible "slice" of
// space in front of the camera. Everything in the slice is white,
// everything else is black. Great for detecting hands above a table, or
// people in one part of a room.
//
// Keys:
//   UP / DOWN       move the far limit (further / closer)
//   RIGHT / LEFT    move the near limit (further / closer)
//
// Before you press Run: make sure the depth server is running.

// "auto" finds the depth server by itself. If it stays at "Looking for the
// depth server", write the name or address shown in the server's window,
// for example "realsense.local" or "192.168.1.50".
String SERVER = "auto";

// The slice, in millimeters. Change these with the arrow keys.
// These starting values suit a camera on a desk looking at hands or
// objects about 30 to 70 cm away. If your camera looks at a wall or a
// person further away and the window stays black, set farMM to about
// 1000 to 1200 here (or press UP a few times).
int nearMM = 300;
int farMM = 700;

DepthClient camera;
PImage slice;   // the black and white picture we build ourselves

void setup() {
  size(640, 480);
  // We only need the exact distances: we build our own picture from them.
  camera = new DepthClient(this, SERVER, "depth16");
}

void draw() {
  background(0);

  if (camera.depthMM == null) {
    fill(255);
    textAlign(CENTER, CENTER);
    text("Looking for the depth server (" + SERVER + ") ...", width / 2, height / 2);
    return;
  }

  // Make an image the same size as the depth image (the first time, and
  // again if the server switches to another size).
  if (slice == null || slice.width != camera.depthWidth || slice.height != camera.depthHeight) {
    slice = createImage(camera.depthWidth, camera.depthHeight, RGB);
  }

  // Go through every pixel: white if inside the slice, black if not.
  int[] distances = camera.depthMM;
  int pixelsInSlice = 0;
  slice.loadPixels();
  for (int i = 0; i < distances.length; i++) {
    int mm = distances[i];
    if (mm >= nearMM && mm <= farMM) {
      slice.pixels[i] = color(255);
      pixelsInSlice++;
    } else {
      slice.pixels[i] = color(0);
    }
  }
  slice.updatePixels();

  image(slice, 0, 0, width, height);

  // Show the current slice and how much of the image is inside it,
  // on dark boxes so the text stays readable on top of white pixels.
  noStroke();
  fill(0);
  rect(0, 0, 300, 56);
  rect(0, height - 32, 300, 32);
  fill(255, 60, 60);
  textAlign(LEFT, TOP);
  textSize(16);
  text("near: " + nearMM + " mm   far: " + farMM + " mm", 10, 10);
  text("pixels inside: " + pixelsInSlice, 10, 32);
  text("arrow keys change near and far", 10, height - 26);
}

void keyPressed() {
  // Each key press moves a limit by 20 mm.
  if (keyCode == UP)    farMM = farMM + 20;
  if (keyCode == DOWN)  farMM = farMM - 20;
  if (keyCode == RIGHT) nearMM = nearMM + 20;
  if (keyCode == LEFT)  nearMM = nearMM - 20;

  // Keep the numbers sensible: near is never below 0
  // and always at least 20 mm in front of far.
  nearMM = max(0, nearMM);
  farMM = max(farMM, nearMM + 20);
}
