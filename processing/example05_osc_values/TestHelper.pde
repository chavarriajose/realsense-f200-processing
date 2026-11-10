// SPDX-License-Identifier: MIT
// TestHelper.pde
//
// Only used by the project's automatic tests, which run this sketch from
// the command line. When you press Run in Processing, it does nothing and
// you can ignore this tab.
//
// The tests start the sketch with:
//   --server=<ip>          to use another server address
//   --screenshot=<file>    to save one picture once values arrive, then quit

public static class TestHelper {

  // Returns the --server=... address if the tests gave one, otherwise the
  // address from the sketch. Also starts the screenshot helper if needed.
  static String serverAddress(PApplet sketch, String normalAddress) {
    String address = normalAddress;
    if (sketch.args == null) return address;
    for (String option : sketch.args) {
      if (option.startsWith("--server=")) address = option.substring(9);
      if (option.startsWith("--screenshot=")) {
        sketch.registerMethod("post", new Screenshot(sketch, option.substring(13)));
      }
    }
    return address;
  }

  public static class Screenshot {
    PApplet sketch;
    String path;
    Screenshot(PApplet sketch, String path) {
      this.sketch = sketch;
      this.path = path;
    }
    // Called by Processing after every draw(): wait about 3 seconds so
    // the values have arrived, then save the window and quit.
    public void post() {
      if (sketch.millis() > 3000) {
        sketch.saveFrame(path);
        System.out.println("Saved test screenshot: " + path);
        sketch.exit();
      }
    }
  }
}
