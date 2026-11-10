// SPDX-License-Identifier: MIT
// example02_nearest_point
//
// Finds the closest thing in front of the camera and draws a circle on it.
// Hold your hand in front of the camera and the circle follows your hand.
//
// The camera has a little noise, so now and then the circle jumps to a
// single stray pixel for a moment. That is normal.
//
// New idea in this example: depthMM, a list with the distance (in
// millimeters) of every pixel. We look at every pixel and remember the
// one with the smallest distance.
//
// Before you press Run: make sure the depth server is running.

// "auto" finds the depth server by itself. If it stays at "Looking for the
// depth server", write the name or address shown in the server's window,
// for example "realsense.local" or "192.168.1.50".
String SERVER = "auto";

// Only look for things between these two distances (in millimeters).
// Things closer than NEAR_MM or further than FAR_MM are ignored.
int NEAR_MM = 200;
int FAR_MM = 1200;

DepthClient camera;

void setup() {
  size(640, 480);
  // "depth8" is the picture we show, "depth16" gives us exact distances.
  camera = new DepthClient(this, SERVER, "depth8", "depth16");
}

void draw() {
  background(0);

  if (camera.depthImage == null || camera.depthMM == null) {
    fill(255);
    textAlign(CENTER, CENTER);
    text("Looking for the depth server (" + SERVER + ") ...", width / 2, height / 2);
    return;
  }

  image(camera.depthImage, 0, 0, width, height);

  // Look at every pixel and remember the closest one.
  int[] distances = camera.depthMM;
  int closestMM = FAR_MM + 1;   // start with something "too far"
  int closestX = -1;
  int closestY = -1;

  for (int y = 0; y < camera.depthHeight; y++) {
    for (int x = 0; x < camera.depthWidth; x++) {
      int mm = distances[y * camera.depthWidth + x];
      // 0 means "no depth here", so we skip it, and we skip
      // everything outside our range.
      if (mm >= NEAR_MM && mm <= FAR_MM && mm < closestMM) {
        closestMM = mm;
        closestX = x;
        closestY = y;
      }
    }
  }

  if (closestX == -1) {
    fill(255);
    textAlign(LEFT, TOP);
    text("Nothing between " + NEAR_MM + " and " + FAR_MM + " mm", 10, 10);
    return;
  }

  // The depth image might be a different size than our window,
  // so we convert the pixel position to a window position.
  float circleX = map(closestX, 0, camera.depthWidth, 0, width);
  float circleY = map(closestY, 0, camera.depthHeight, 0, height);

  noFill();
  stroke(255, 60, 60);
  strokeWeight(4);
  circle(circleX, circleY, 50);

  // Show the distance next to the circle. constrain() keeps the text
  // inside the window when the circle is close to an edge.
  fill(255, 60, 60);
  noStroke();
  textAlign(LEFT, CENTER);
  textSize(16);
  float textX = constrain(circleX + 32, 0, width - 70);
  float textY = constrain(circleY, 12, height - 12);
  text(closestMM + " mm", textX, textY);
}
