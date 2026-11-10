# Setting up the Linux computer

This guide takes you from a fresh Ubuntu installation to a running depth
server that starts by itself when the computer boots. It needs
**Ubuntu 24.04 LTS or newer** (the server needs Python 3.11 or newer, and
Ubuntu 22.04 has Python 3.10). Plan about 30 minutes.

You type the commands in a **terminal** (press `Ctrl+Alt+T` to open one).
Copy each command exactly, press Enter, and wait until it is finished
before typing the next one. Commands that start with `sudo` install or
change things for the whole computer: they ask for your password (nothing
appears on screen while you type it, that is normal).

## 1. Plug in the camera

Plug the F200 into a **USB 3.0** port, directly on the computer (not
through a hub). USB 3.0 ports are often blue inside or marked "SS".

Check that Linux sees it:

```bash
lsusb | grep -i realsense
```

Expected output (the bus and device numbers may differ):

```
Bus 004 Device 005: ID 8086:0a66 Intel Corp. RealSense 3D Camera (Front F200)
```

If nothing appears, try another USB port.

## 2. Install the system packages

```bash
sudo apt update
sudo apt install git python3-opencv python3-numpy python3-websockets python3-venv v4l-utils
```

Check that the camera's video devices exist:

```bash
v4l2-ctl --list-devices
```

You should see a block called `Intel(R) RealSense(TM) 3D Camer (usb-...)`
with several `/dev/video...` lines. (The missing "a" at the end of "Camera"
is normal: Linux cuts device names off after 31 letters.)

## 3. Get the project

Put the project in your home folder:

```bash
cd ~
git clone https://github.com/chavarriajose/realsense-f200-processing.git
cd realsense-f200-processing
```

(If you got the project as a ZIP file instead, unzip it into your home
folder and rename the folder to `realsense-f200-processing`.)

From now on, all commands are typed inside this folder. If you open a new
terminal, first type `cd ~/realsense-f200-processing`.

## 4. Create the Python environment

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-linux.txt
```

This makes a private Python folder called `.venv` inside the project and
installs `python-osc` into it (the one package Ubuntu does not provide).
The last line of output should say `Successfully installed python-osc-...`.

## 5. Test the camera

```bash
python3 tools/preview.py
```

A window opens with three pictures: depth, infrared and color. Hold your
hand about 50 cm in front of the camera: it should appear bright in the
depth picture, and the distance at the center is written in the top left
corner. Press `q` to close the window.

## 6. Start the server by hand

```bash
./start-server.sh
```

Expected output (your names and addresses will be different):

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

Leave this terminal open while you test with a sketch (see
`docs/first-sketch.md`). Press `Ctrl+C` to stop the server.

## 7. Add a desktop icon

So you do not need the terminal to start the server, add an icon once:

```bash
tools/linux/install_launcher.sh
```

Expected output:

```
Added to the app menu: /home/<you>/.local/share/applications/realsense-depth-server.desktop
Added to the desktop: /home/<you>/Desktop/realsense-depth-server.desktop

Done. Double click "RealSense Depth Server" on the desktop to start the server.
```

From now on, **double click "RealSense Depth Server"** on the desktop (or
press the Super key, type `depth` and press Enter). A window opens, starts
the server and shows what to write in sketches. Close the window to stop
the server.

If Ubuntu asks whether to trust the icon, right click it and choose
**Allow Launching**. Use the icon on the desktop itself or in the app menu:
the Files app never runs programs on a double click, so opening
`start-server.sh` or the icon from a Files window only shows its text.
Tip: right click the app in the dock and choose **Pin to Dash** to keep it
one click away. If you move the project to another folder, run
`tools/linux/install_launcher.sh` again.

## 8. How sketches find the server

The examples start with `String SERVER = "auto";`. With "auto", the sketch
listens for a small "I am here" message that the server sends to the whole
network every second, and connects to it. Nobody needs to type an address.

Some networks (often shared or public Wi-Fi) block these messages. Then "auto" tries
the name `realsense.local`, which works if you give the Linux computer that
name (recommended, do it once):

```bash
sudo hostnamectl set-hostname realsense
sudo sed -i "s/^127.0.1.1.*/127.0.1.1 realsense/" /etc/hosts
```

(The second line updates the computer's own list of names, otherwise
`sudo` complains `unable to resolve host realsense`.) Restart the computer
afterwards. The server window will then show
`String SERVER = "realsense.local";`, and that name keeps working even if
the computer gets a new IP address.

If neither works on your network, people can still type the IP address
shown in the server window. To keep that address from changing, give the
computer a fixed address:

**Option A (recommended): ask the network.** On a managed network (office,
school, university), ask the IT department for a "DHCP reservation" for this computer. They will need its
MAC address, which you can see with:

```bash
ip link
```

(It looks like `a4:bb:6d:12:34:56`, on the line after your network
connection's name.) At home, most routers have the same option in their
settings page.

**Option B: set it on the computer.** Only do this if you know which
addresses are free on your network. Find the name of your connection:

```bash
nmcli connection show
```

Then set the address (replace the connection name and the numbers with
yours: `192.168.1.50` is the address you want, `192.168.1.1` is your
router):

```bash
sudo nmcli connection modify "Your connection name" ipv4.method manual \
  ipv4.addresses 192.168.1.50/24 ipv4.gateway 192.168.1.1 ipv4.dns 192.168.1.1
sudo nmcli connection up "Your connection name"
```

## 9. Make sure the network lets other computers in

- **Same network:** the computers running sketches must be on the same
  network as the Linux computer. Many shared Wi-Fi networks block devices
  from talking to each other ("client isolation"). If sketches never
  connect, ask IT, or use your own small Wi-Fi router for the setup.
- **Firewall on the Linux computer:** Ubuntu's firewall is off by default.
  If it is on (`sudo ufw status` says `Status: active`), open the two ports:

  ```bash
  sudo ufw allow 8765/tcp
  sudo ufw allow 9000/udp
  ```

## 10. Start the server automatically at boot

The file `server/realsense-depth.service` tells Linux how to run the server
in the background, start it at boot, and restart it if it ever stops.

First, fill in your user name and the project folder. This command does it
for you and saves the result as a new file:

```bash
sed "s|YOUR_USER|$USER|; s|/path/to/realsense-f200-processing|$PWD|g" \
  server/realsense-depth.service > /tmp/realsense-depth.service
```

Then install and start it:

```bash
sudo cp /tmp/realsense-depth.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now realsense-depth
```

Check that it runs:

```bash
systemctl status realsense-depth
```

You should see `active (running)` in green. To see what the server prints
(press `Ctrl+C` to stop watching, the server keeps running):

```bash
journalctl -u realsense-depth -f
```

Restart the computer once and check `systemctl status realsense-depth`
again to be sure it starts by itself.

Useful commands:

| What                                   | Command                                  |
|----------------------------------------|------------------------------------------|
| stop the server                        | `sudo systemctl stop realsense-depth`    |
| start it again                         | `sudo systemctl start realsense-depth`   |
| restart (after changing config.toml)   | `sudo systemctl restart realsense-depth` |
| do not start at boot anymore           | `sudo systemctl disable realsense-depth` |

The preview tool and the service cannot use the camera at the same time:
stop the service before running `tools/preview.py`.

## 11. Settings

All settings are in `server/config.toml`: the distance range, which images
may be sent, the ports, and how often the server sends. Each line has a
comment that explains it. Restart the server after a change.

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `Could not find the RealSense F200 depth camera` | Check the USB 3.0 port and `lsusb`. Unplug and plug in again. |
| `Camera not available ... Trying again in 3 seconds` | The camera is unplugged, or another program uses it (the preview, or the service while you start a second server). |
| `Address already in use` | The server is already running: in another window, or as the service. |
| `No module named 'pythonosc'` | Start with `.venv/bin/python`, not `python3`, or redo step 4. |
| Only a part of the image has depth | Normal for far surfaces. The F200 works best between about 20 and 80 cm. |
| Distances look a few percent off | See `DEPTH_UNITS_PER_MM` in `server/capture_linux.py`. |
| Sketches stay at "Looking for the depth server" | Check that the server runs. Then try the name or address from the server window instead of "auto" (step 8), and check the network (step 9). |
