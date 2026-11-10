// SPDX-License-Identifier: MIT
// example01_show_depth
//
// Shows the depth image from the RealSense F200 camera.
// Things close to the camera are bright, things further away are darker,
// and places where the camera cannot measure (too far, too close, or a
// shiny surface) are black.
//
// Before you press Run: make sure the depth server is running on the
// Linux computer the camera is plugged into.

// "auto" finds the depth server by itself. If it stays at "Looking for the
// depth server", write the name or address shown in the server's window,
// for example "realsense.local" or "192.168.1.50".
String SERVER = "auto";

DepthClient camera;

void setup() {
  size(640, 480);
  // Connect to the server and ask for "depth8": the depth image as a
  // ready to use grayscale picture.
  camera = new DepthClient(this, SERVER, "depth8");
}

void draw() {
  background(0);

  if (camera.depthImage == null) {
    // Nothing has arrived yet: show a message instead of an empty window.
    fill(255);
    textAlign(CENTER, CENTER);
    text("Looking for the depth server (" + SERVER + ") ...", width / 2, height / 2);
    return;
  }

  // Draw the depth image so it fills the whole window.
  image(camera.depthImage, 0, 0, width, height);
}
