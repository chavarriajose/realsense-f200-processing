// SPDX-License-Identifier: MIT
// DepthClient.pde
//
// This tab connects your sketch to the depth server and turns what it
// receives into things that are easy to use in Processing:
//
//   camera.depthImage   a PImage of the depth (near = bright, far = dark)
//   camera.depthMM      an int[] with the distance in millimeters of every
//                       pixel (0 means "no depth here")
//   camera.irImage      a PImage of the infrared camera
//   camera.colorImage   a PImage of the color camera
//   camera.depthWidth, camera.depthHeight   size of the depth image (640 x 480)
//   camera.getDistance(x, y)   distance in mm at one pixel of the depth image
//   camera.isConnected()       true while the server is connected
//
// SERVER can be "auto" (the ServerFinder tab finds the server by itself),
// a name like "realsense.local", or an address like "192.168.1.50".
//
// You do not need to change anything in this tab. Each example sketch has
// its own copy, so every sketch folder works on its own.
//
// How it works, if you are curious: the server sends images over a
// WebSocket, a connection that stays open so the server can push new frames
// all the time. We use the WebSocket client that is built into Java, so no
// extra library is needed. The message format is described in
// docs/protocol.md in the project.

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.nio.ByteBuffer;
import java.io.ByteArrayOutputStream;
import java.io.ByteArrayInputStream;
import java.util.concurrent.CompletionStage;
import java.util.zip.Inflater;
import javax.imageio.ImageIO;

// "public" lets Processing call post() below during the automatic tests.
public class DepthClient implements WebSocket.Listener {

  // ----- Things you can use in your sketch ---------------------------------
  PImage depthImage;     // null until the first image arrives
  PImage irImage;
  PImage colorImage;
  int[] depthMM;         // distance in millimeters for every pixel
  int depthWidth = 640;
  int depthHeight = 480;
  JSONObject values;     // nearest, presence, blob, average (if asked for)

  // ----- Internal bookkeeping ----------------------------------------------
  PApplet sketch;
  String serverAddress;   // what the sketch wrote in SERVER, for example "auto"
  ServerFinder finder;    // turns "auto" into a real address (ServerFinder tab)
  String[] streams;
  WebSocket socket;
  volatile boolean connected = false;
  ByteArrayOutputStream incoming = new ByteArrayOutputStream();
  StringBuilder incomingText = new StringBuilder();
  int framesReceived = 0;
  String screenshotPath = null;   // only used by the automatic tests

  // The server's WebSocket port. Change it only if you changed
  // websocket_port in the server's config.toml.
  final int PORT = 8765;

  // Create a client. "streams" are the things you want, for example
  // "depth8" (the depth picture) or "depth16" (exact distances).
  DepthClient(PApplet sketch, String serverAddress, String... streams) {
    this.sketch = sketch;
    this.serverAddress = serverAddress;
    this.streams = streams;
    readTestOptions();
    finder = new ServerFinder(this.serverAddress);
    // Connect in the background, and connect again if the connection drops,
    // so the sketch keeps working when the server restarts.
    Thread keepConnected = new Thread(new Runnable() {
      public void run() {
        keepConnectedLoop();
      }
    });
    keepConnected.setDaemon(true);
    keepConnected.start();
  }

  boolean isConnected() {
    return connected;
  }

  // Distance in millimeters at pixel (x, y) of the depth image.
  // Returns 0 if there is no depth there, or if (x, y) is outside the image.
  int getDistance(int x, int y) {
    int[] distances = depthMM;   // copy the reference: a new frame may arrive meanwhile
    if (distances == null || x < 0 || y < 0 || x >= depthWidth || y >= depthHeight) {
      return 0;
    }
    return distances[y * depthWidth + x];
  }

  // ----- Connecting --------------------------------------------------------

  void keepConnectedLoop() {
    while (true) {
      String host = finder.getAddress();   // null while "auto" is still looking
      if (!connected && host != null) {
        String address = "ws://" + host + ":" + PORT;
        try {
          println("Connecting to " + address + " ...");
          socket = HttpClient.newHttpClient()
            .newWebSocketBuilder()
            .buildAsync(URI.create(address), this)
            .join();
        }
        catch (Exception problem) {
          println("Could not connect to the depth server at " + address);
          println("  Is the server running, and is SERVER right? (\"auto\", a name or an IP address)");
        }
      }
      sketch.delay(2000);  // check again in 2 seconds
    }
  }

  public void onOpen(WebSocket webSocket) {
    connected = true;
    println("Connected to the depth server.");
    // Tell the server which streams we want, as a small JSON text.
    StringList names = new StringList(streams);
    webSocket.sendText("{\"streams\": [\"" + names.join("\", \"") + "\"]}", true);
    webSocket.request(1);  // ready for the first message
  }

  public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
    connected = false;
    println("The depth server closed the connection.");
    return null;
  }

  public void onError(WebSocket webSocket, Throwable error) {
    connected = false;
    println("Lost the connection to the depth server.");
  }

  // ----- Receiving ---------------------------------------------------------

  // Images arrive as binary messages. Big messages can arrive in several
  // pieces, so we collect the pieces until "last" is true.
  public CompletionStage<?> onBinary(WebSocket webSocket, ByteBuffer data, boolean last) {
    byte[] piece = new byte[data.remaining()];
    data.get(piece);
    incoming.write(piece, 0, piece.length);
    if (last) {
      try {
        handleImage(incoming.toByteArray());
      }
      catch (Exception problem) {
        println("Could not read an image from the server: " + problem);
      }
      incoming.reset();
    }
    webSocket.request(1);  // ready for the next message
    return null;
  }

  // The values (nearest point, presence, ...) arrive as JSON text.
  public CompletionStage<?> onText(WebSocket webSocket, CharSequence text, boolean last) {
    incomingText.append(text);
    if (last) {
      values = parseJSONObject(incomingText.toString());
      incomingText.setLength(0);
    }
    webSocket.request(1);
    return null;
  }

  void handleImage(byte[] message) throws Exception {
    // The first 8 bytes are the header (see docs/protocol.md).
    ByteBuffer header = ByteBuffer.wrap(message, 0, 8);
    int stream = header.get() & 0xFF;
    int encoding = header.get() & 0xFF;
    int w = header.getShort() & 0xFFFF;
    int h = header.getShort() & 0xFFFF;
    byte[] payload = java.util.Arrays.copyOfRange(message, 8, message.length);

    if (encoding == 2) {               // JPEG (color)
      colorImage = new PImage(ImageIO.read(new ByteArrayInputStream(payload)));
      return;
    }
    if (encoding == 1) {               // zlib: unpack first
      int bytesPerPixel = (stream == 2) ? 2 : 1;
      payload = unzip(payload, w * h * bytesPerPixel);
    }

    if (stream == 1) {                 // depth8: one gray byte per pixel
      depthImage = grayImage(payload, w, h);
      depthWidth = w;
      depthHeight = h;
      framesReceived++;
    } else if (stream == 2) {          // depth16: two bytes per pixel, in mm
      int[] distances = new int[w * h];
      for (int i = 0; i < distances.length; i++) {
        // high byte first ("big endian"), the & 0xFF makes the bytes positive
        distances[i] = ((payload[2 * i] & 0xFF) << 8) | (payload[2 * i + 1] & 0xFF);
      }
      depthWidth = w;
      depthHeight = h;
      depthMM = distances;             // swap in the new frame all at once
      framesReceived++;
    } else if (stream == 3) {          // infrared: one gray byte per pixel
      irImage = grayImage(payload, w, h);
      framesReceived++;
    }
  }

  // Build a new grayscale PImage from one byte per pixel.
  // We make a new image every time and then swap it in, so draw() never
  // sees a half finished picture.
  PImage grayImage(byte[] grays, int w, int h) {
    PImage picture = createImage(w, h, RGB);
    picture.loadPixels();
    for (int i = 0; i < w * h; i++) {
      int g = grays[i] & 0xFF;
      picture.pixels[i] = 0xFF000000 | (g << 16) | (g << 8) | g;
    }
    picture.updatePixels();
    return picture;
  }

  byte[] unzip(byte[] packed, int size) throws Exception {
    Inflater inflater = new Inflater();
    inflater.setInput(packed);
    byte[] result = new byte[size];
    int done = 0;
    while (done < size && !inflater.finished()) {
      done += inflater.inflate(result, done, size - done);
    }
    inflater.end();
    return result;
  }

  // ----- Automatic tests -----------------------------------------------------
  // The project's tests run sketches from the command line with
  //   --server=<ip>          to use another server address
  //   --screenshot=<file>    to save one picture after a few frames and quit
  // When you press Run in Processing, none of this is used.

  void readTestOptions() {
    if (sketch.args == null) return;
    for (String option : sketch.args) {
      if (option.startsWith("--server=")) serverAddress = option.substring(9);
      if (option.startsWith("--screenshot=")) screenshotPath = option.substring(13);
    }
    if (screenshotPath != null) sketch.registerMethod("post", this);
  }

  // Called by Processing after every draw(), only during tests.
  public void post() {
    if (framesReceived > 30) {   // about 2 seconds of frames
      sketch.saveFrame(screenshotPath);
      println("Saved test screenshot: " + screenshotPath);
      sketch.exit();
    }
  }
}
