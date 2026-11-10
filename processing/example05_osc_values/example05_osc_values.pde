// SPDX-License-Identifier: MIT
// example05_osc_values
//
// Uses only the numbers the server calculates, no images at all:
//   nearest   where the closest point is, and how far
//   presence  is anything there? (1 = yes, 0 = no)
//   blob      center and size of the biggest object
//   average   average distance of everything in range
//
// These arrive as OSC messages, a simple way to send numbers over the
// network that many tools understand (Processing, Max, Pure Data,
// TouchDesigner, ...). This is the lightest way to use the camera: perfect
// when you only need "where is the hand?" and not the picture.
//
// This example needs the oscP5 library. Install it once from the menu
// Sketch > Import Library > Manage Libraries..., search "oscP5", Install.
//
// Before you press Run: make sure the depth server is running.

import oscP5.*;
import netP5.*;

// "auto" finds the depth server by itself. If it stays at "Waiting for
// values from the depth server", write the name or address shown in the server's window,
// for example "realsense.local" or "192.168.1.50".
String SERVER = "auto";

// The server listens for our "hello" on this port (osc_port in config.toml).
int SERVER_PORT = 9000;
// We listen for the values on this port. Any free port works.
int MY_PORT = 12000;

OscP5 osc;
ServerFinder finder;   // turns "auto" into the server's address (ServerFinder tab)
int lastHello = -10000;   // time (in ms) of our last hello to the server

// The size of the depth image on the server. If the server uses 640 x 240
// (height = 240 in its config.toml), change DEPTH_HEIGHT to 240.
int DEPTH_WIDTH = 640;
int DEPTH_HEIGHT = 480;

// The latest values. x goes from 0 to DEPTH_WIDTH - 1,
// y from 0 to DEPTH_HEIGHT - 1.
int nearestX = -1, nearestY = -1, nearestMM = 0;
int presence = 0;
int blobX = -1, blobY = -1, blobMM = 0, blobSize = 0;
int averageMM = 0;
int messagesReceived = 0;

void setup() {
  size(640, 480);
  SERVER = TestHelper.serverAddress(this, SERVER);   // only changes anything during automatic tests
  osc = new OscP5(this, MY_PORT);   // start listening
  finder = new ServerFinder(SERVER);
}

void draw() {
  background(30);

  // Say hello every 2 seconds. The server sends values only to sketches
  // that said hello in the last 10 seconds, so we keep reminding it.
  // (getAddress() is null while "auto" is still looking for the server.)
  String serverAddress = finder.getAddress();
  if (serverAddress != null && millis() - lastHello > 2000) {
    OscMessage hello = new OscMessage("/subscribe");
    hello.add(MY_PORT);   // "please send the values to this port"
    osc.send(hello, new NetAddress(serverAddress, SERVER_PORT));
    lastHello = millis();
  }

  if (messagesReceived == 0) {
    fill(255);
    textAlign(CENTER, CENTER);
    text("Waiting for values from the depth server (" + SERVER + ") ...", width / 2, height / 2);
    return;
  }

  // Presence: the background turns green when something is there.
  if (presence == 1) {
    background(20, 70, 40);
  }

  // Blob: a rectangle whose area matches the size of the blob, drawn at
  // the blob's center. (x and y are mapped from the depth image
  // to the window.)
  if (blobSize > 0) {
    float x = map(blobX, 0, DEPTH_WIDTH, 0, width);
    float y = map(blobY, 0, DEPTH_HEIGHT, 0, height);
    float side = sqrt(blobSize) * width / float(DEPTH_WIDTH);
    noFill();
    stroke(120, 200, 255);
    strokeWeight(3);
    rectMode(CENTER);
    rect(x, y, side, side);
  }

  // Nearest point: a circle that gets bigger when the point is closer.
  if (nearestMM > 0) {
    float x = map(nearestX, 0, DEPTH_WIDTH, 0, width);
    float y = map(nearestY, 0, DEPTH_HEIGHT, 0, height);
    float size = map(nearestMM, 200, 1200, 120, 20);
    noStroke();
    fill(255, 80, 80);
    circle(x, y, size);
  }

  // Average distance: a bar at the bottom, longer when things are further.
  noStroke();
  fill(255, 200, 0);
  rectMode(CORNER);
  rect(0, height - 20, map(averageMM, 0, 1200, 0, width), 20);

  // All the numbers as text, on a dark box so they stay readable.
  noStroke();
  fill(0, 200);
  rect(0, 0, 420, 92);
  fill(255);
  textAlign(LEFT, TOP);
  textSize(15);
  text("nearest:  x " + nearestX + "  y " + nearestY + "  " + nearestMM + " mm", 10, 10);
  text("presence: " + presence, 10, 30);
  text("blob:     x " + blobX + "  y " + blobY + "  " + blobMM + " mm  size " + blobSize, 10, 50);
  text("average:  " + averageMM + " mm", 10, 70);
}

// oscP5 calls this function every time a message arrives.
void oscEvent(OscMessage message) {
  if (message.checkAddrPattern("/nearest")) {
    nearestX = message.get(0).intValue();
    nearestY = message.get(1).intValue();
    nearestMM = message.get(2).intValue();
  } else if (message.checkAddrPattern("/presence")) {
    presence = message.get(0).intValue();
  } else if (message.checkAddrPattern("/blob")) {
    blobX = message.get(0).intValue();
    blobY = message.get(1).intValue();
    blobMM = message.get(2).intValue();
    blobSize = message.get(3).intValue();
  } else if (message.checkAddrPattern("/average")) {
    averageMM = message.get(0).intValue();
  }
  messagesReceived++;
}
