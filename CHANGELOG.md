# Changelog

What changed in each version. The newest version is at the top.

## 0.9.1 beta

- **Ready-made downloads for all three systems.** New: a Linux download
  (`RealSense-Depth-Server-Linux-x64.tar.gz`) with the server and everything
  it needs, a start script and a one-time desktop icon installer. It works
  on 64-bit Ubuntu 22.04 or newer. It has not been tried with a camera yet:
  please tell us how it goes.
- The Mac app, the Windows program and the Linux download are now built
  automatically on GitHub for every release, so they always match the code.
- Linux: the server no longer needs the `v4l-utils` package to find the
  camera (it asks the video driver directly when `v4l2-ctl` is missing).
- The server writes its messages out right away, so they also reach log
  files and the systemd journal when it is stopped.
- The Windows zip uses standard folder names inside, so it also unpacks
  with other unzip programs.
- Guides: the Linux guide starts with the ready-made download; the full
  setup (with automatic start at boot) follows.

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
