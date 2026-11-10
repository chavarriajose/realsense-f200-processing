# server

The depth server. It runs on the computer the camera is plugged into (Linux,
Mac or Windows), reads the camera and sends depth images and values to sketches on
the network.

| File                       | What it is                                                        |
|----------------------------|-------------------------------------------------------------------|
| `depth_server.py`          | the server itself, start this one                                 |
| `config.toml`              | all the settings (range, ports, which images to send)             |
| `capture.py`               | picks the right camera code for Linux, Mac or Windows             |
| `capture_linux.py`         | everything that talks to the camera on Linux                      |
| `capture_macos.py`         | everything that talks to the camera on a Mac (over USB, needs sudo) |
| `capture_windows.py`       | everything that talks to the camera on Windows (Media Foundation) |
| `processing_steps.py`      | turns depth into the images and values that are sent             |
| `discovery.py`             | announces the server on the network, for `SERVER = "auto"`        |
| `realsense-depth.service`  | lets the server start automatically at boot (see below)           |

The full setup of a fresh Linux computer is in `docs/linux/setup.md`.
On a Mac, see `docs/macos/setup.md` (most people use the ready-made app; the
"For developers" part there shows how to run this folder from a terminal).
On Windows, see `docs/windows/setup.md` (the same: most people use the
ready-made program, and "For developers" shows the terminal way).
The rest of this page is about Linux.
The message formats are in `docs/protocol.md`.

## Before you start (once)

From the main project folder:

```bash
sudo apt install python3-opencv python3-numpy python3-websockets python3-venv v4l-utils
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-linux.txt
```

The first line installs system packages and asks for your password. The
other two lines create a small private Python folder (`.venv`) and install
the one package Ubuntu does not have (`python-osc`) into it.

## Start the server

The easiest way: double click the **RealSense Depth Server** icon on the
desktop. To create that icon once, run `tools/linux/install_launcher.sh` from the
main project folder (see `docs/linux/setup.md`, step 7).

Or start it in a terminal, from the main project folder:

```bash
./start-server.sh
```

You should see something like:

```
Settings from config.toml:
  [range] near_mm=200, far_mm=1200
  ...

================================================================
  Depth server is running.

  What to write at the top of a sketch:
    String SERVER = "auto";        (finds this server by itself)
  If "auto" does not work on your network, use one of these:
    String SERVER = "realsense.local";
    String SERVER = "192.168.1.50";

  Images: WebSocket port 8765, values: OSC port 9000
  To stop the server, close this window or press Ctrl+C.
================================================================

Camera ready.
```

Sketches use `"auto"` by default and find the server by themselves: the
server announces itself on the network once per second (see `discovery.py`).
The other two lines are for networks that block those announcements.
When sketches connect, the server prints a line for each one.

Close the window or press `Ctrl+C` to stop the server.

### If something goes wrong

- `Camera not available ... Trying again in 3 seconds`: the camera is not
  plugged in, or another program (for example `tools/preview.py`) is using
  it. The server keeps trying, and starts sending as soon as the camera is free.
- `Could not start the server: [Errno 98] Address already in use`: the
  server is already running, probably as a service (see below).
- `ModuleNotFoundError: No module named 'pythonosc'`: you started it with
  `python3` instead of `.venv/bin/python`, or skipped "Before you start".

## Change settings

Open `config.toml` in any text editor. Every setting has a comment that
explains it. Save, then restart the server. You can also give another
settings file: `.venv/bin/python server/depth_server.py my_settings.toml`

## Test without Processing

While the server runs, in a second terminal:

```bash
.venv/bin/python tools/test_client.py 127.0.0.1 depth8 depth16 values osc
```

After 5 seconds it prints how many messages arrived (about 15 per second
for each stream), the last values, and saves `test_depth8.png` and
`test_depth16.png`.

## Start automatically at boot

`realsense-depth.service` tells Linux (systemd) to start the server at boot
and restart it if it ever stops. The steps are in `docs/linux/setup.md`.
