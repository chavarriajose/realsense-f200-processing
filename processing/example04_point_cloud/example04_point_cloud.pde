// SPDX-License-Identifier: MIT
// example04_point_cloud
//
// Turns the depth image into a 3D "point cloud": every pixel becomes a
// dot in 3D space, at the distance the camera measured. Drag with the
// mouse to look at it from another side.
//
// New ideas in this example: P3D (Processing's 3D mode), and how to turn
// a pixel plus a distance into a 3D position.
//
// Before you press Run: make sure the depth server is running.

// "auto" finds the depth server by itself. If it stays at "Looking for the
// depth server", write the name or address shown in the server's window,
// for example "realsense.local" or "192.168.1.50".
String SERVER = "auto";

// Drawing all 307200 pixels is slow, so we only draw every STEP-th pixel
// in each direction. STEP = 4 draws 1 of every 16 pixels. Try 2 or 8.
int STEP = 4;

// How "wide" the camera sees, expressed as a focal length in pixels.
// This is an approximate value for the F200's depth camera at 640 x 480.
// It decides how much the cloud spreads out sideways with distance.
float FOCAL_LENGTH = 475;

// The cloud turns around this distance (in millimeters): the middle of
// the F200's range, which goes from about 200 to 1200 mm.
float CENTER_MM = 700;

// Rotation of the cloud, changed by dragging the mouse.
float turnY = -0.5;
float turnX = 0.2;

DepthClient camera;

void setup() {
  size(800, 600, P3D);
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

  // Put the center of our 3D world in the middle of the window and push it
  // CENTER_MM away from us, so the whole range (200 to 1200 mm) stays in
  // front of Processing's virtual eye. Then turn it the way the mouse says.
  translate(width / 2, height / 2, -CENTER_MM);
  rotateX(turnX);
  rotateY(turnY);

  int[] distances = camera.depthMM;
  int w = camera.depthWidth;
  int h = camera.depthHeight;

  strokeWeight(2);
  for (int y = 0; y < h; y += STEP) {
    for (int x = 0; x < w; x += STEP) {
      int mm = distances[y * w + x];
      if (mm == 0) {
        continue;   // no depth here, nothing to draw
      }

      // From pixel + distance to a 3D point (all in millimeters).
      // A pixel far from the center of the image is far to the side,
      // and more so the further away it is. That is what the camera
      // lens does, and this undoes it.
      float pointX = (x - w / 2) * mm / FOCAL_LENGTH;
      float pointY = (y - h / 2) * mm / FOCAL_LENGTH;
      // The camera is at z = 0 and looks into the screen. We move the
      // cloud back by CENTER_MM so the middle of the range sits at z = 0,
      // which makes it turn around the middle of the range.
      float pointZ = -(mm - CENTER_MM);

      // Close points are bright and warm, far points are dark and blue.
      float closeness = map(mm, 200, 1200, 255, 60);
      stroke(closeness, closeness * 0.8, 255 - closeness * 0.5);
      point(pointX, pointY, pointZ);
    }
  }
}

void mouseDragged() {
  // Moving the mouse left/right turns the cloud around, up/down tilts it.
  turnY = turnY + (mouseX - pmouseX) * 0.01;
  turnX = turnX - (mouseY - pmouseY) * 0.01;
}
