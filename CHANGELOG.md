# Changelog

What changed in each version. The newest version is at the top.

## 0.9.0 beta (first public version)

The first version shared with everyone. Everything works on Linux, macOS
and Windows, each tested on one computer with a real F200 camera.

- **Depth server** for the RealSense F200 (Creative VF0800): reads depth,
  infrared and color, and sends them over the network.
  - Linux: uses the standard Linux video driver.
  - macOS: talks to the camera over USB; a double-click app that asks for
    your password.
  - Windows: uses Windows' own video system (Media Foundation), no driver
    and no administrator rights; a double-click program.
- **WebSocket images**: `depth8` (grayscale picture), `depth16` (millimeters
  for every pixel), `ir` and `color`, each sketch chooses what it wants.
- **OSC values**: `/nearest`, `/presence`, `/blob`, `/average`.
- **`SERVER = "auto"`**: sketches find the server on the network by
  themselves.
- **Five Processing examples**: show depth, nearest point, threshold, point
  cloud, OSC values.
- **Guides** for every system, a first sketch guide, and the exact message
  format for writing your own client.
