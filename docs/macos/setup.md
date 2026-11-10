# The camera on your own Mac

This guide is for plugging the RealSense F200 camera **directly into your
own Mac**, and running your sketches on that same Mac. You need no
Linux computer for this.

(If the camera is connected to a Linux computer on your network instead, skip
this guide and go straight to `docs/first-sketch.md`.)

## What you need

- The RealSense F200 camera (also sold by Creative as "VF0800").
- A **USB 3.0 hub or USB-C to USB-A adapter**, because the camera has a
  USB-A plug and most Macs only have USB-C ports. That is completely fine.
  Make sure the hub says USB 3.0 (or 3.1, 3.2, "SuperSpeed", 5 Gbps): with
  a USB 2.0 hub the camera does not work.
- A Mac with macOS 14 (Sonoma) or newer. Apple Silicon (M1 and newer) and
  Intel Macs both work.
- **Your Mac's password**, and your user account must be an administrator.
  macOS only lets administrators take the camera away from its built-in
  webcam driver. On your own laptop you almost certainly are one. (On a Mac
  managed by a school or company you may not be; then use the Linux setup
  instead.)
- Processing 4 (see `docs/first-sketch.md`, step 1).

## 1. Get the app

1. Download `RealSense-Depth-Server-macOS.zip` from the project's
   **Releases** page on GitHub (right side of the project page).
2. Double click the zip file to unzip it. You get **RealSense Depth Server**
   (an app).
3. Drag **RealSense Depth Server** into your **Applications** folder.

## 2. Open it the first time

The app is free and open source, but it is not registered with Apple (that
costs money every year). So the first time, macOS blocks it and you have to
allow it once:

1. Double click **RealSense Depth Server** in Applications.
2. macOS says something like *"RealSense Depth Server" Not Opened: Apple
   could not verify that it is free of malware.* Click **Done**.
3. Open **System Settings** (Apple menu) and click **Privacy & Security**.
4. Scroll down to the **Security** part. You see *"RealSense Depth Server"
   was blocked to protect your Mac.* Click **Open Anyway**.
5. Confirm with your password or Touch ID, then click **Open Anyway** once
   more.

The exact words can differ a little between macOS versions. You only do
this once; after that the app opens normally.

(If you are comfortable with the Terminal, this command does the same as
steps 2 to 5:
`xattr -dr com.apple.quarantine "/Applications/RealSense Depth Server.app"`)

## 3. Start the server

1. Plug in the camera (through the hub).
2. Double click **RealSense Depth Server**.
3. A **Terminal** window opens and asks for your password:

   ```
   ================================================================
     RealSense Depth Server

     macOS needs your password to let this program use the camera.
     Type your Mac password and press Enter.
     (You will not see the letters while you type. That is normal.)
   ================================================================

   Password:
   ```

   Type your Mac password and press **Enter**. You will not see any dots
   or letters while you type. That is normal.

4. After a few seconds you see something like this:

   ```
   ================================================================
     Depth server is running.

     What to write at the top of a sketch:
       String SERVER = "auto";        (finds this server by itself)
     ...
   ================================================================

   Camera ready.
   ```

If macOS asks **"Do you want the application depth-server to accept
incoming network connections?"**, click **Allow**. This is only needed if
sketches on *other* computers should use your camera too. Sketches on your
own Mac work either way.

Leave the Terminal window open while you work. It is the server.

## 4. Run a sketch

Follow `docs/first-sketch.md` from step 2. `String SERVER = "auto";`
finds the server on your own Mac by itself. If it does not, write:

```java
String SERVER = "127.0.0.1";
```

(`127.0.0.1` always means "this computer".)

## 5. Stop the server

Close the Terminal window. Terminal asks *"Do you want to terminate
running processes in this window?"*: click **Terminate**.

Or click into the window and press **Ctrl+C**. The window then shows
`Server stopped.` and `Press Enter to close this window.`

Either way the server lets go of the camera, and macOS can use it as a
normal webcam again (it shows up as "Intel(R) RealSense(TM) 3D Camera (Front F200)
Depth").

## If it does not work

| What you see | What to try |
|--------------|-------------|
| A message *"Please move RealSense Depth Server into your Applications folder..."* (no Terminal window) | The app is still in Downloads. Drag it into Applications in Finder and open it from there. If it is already there, someone else installed it with their account: ask them to open it once. |
| `Could not find the RealSense F200 camera` | Check the cable and the hub. Open **System Information** (hold Option, click the Apple menu), click **USB**: the camera should be listed as "Intel(R) RealSense(TM) 3D Camera (Front F200)". If it is not there, try another port on the hub, or another hub (it must be USB 3.0). |
| `Could not start the server: [Errno 48] Address already in use` | The server is already running in another Terminal window. Use that one, or close it first. |
| `Camera not available: The camera is busy` (repeating every 3 seconds) | Another program is using the camera, for example the preview tool (`tools/preview.py`). Close it; the server then starts by itself. |
| `Sorry, try again.` | The password was wrong. Type it again (you have three tries). |
| `... is not in the sudoers file` | Your account is not an administrator on this Mac. Ask whoever manages the Mac, or use the Linux setup. |
| `Lost the camera` followed by `Camera ready.` | A short USB hiccup. The server recovered by itself. If it happens often, try another port or hub. |
| The window says `Press Enter to close this window.` right away | Read the lines above it, they say why. |

## For developers

Run the server from a terminal instead of the app (from the main project
folder; needs [Homebrew](https://brew.sh)):

```bash
brew install libusb
python3 -m venv .venv
.venv/bin/pip install -r requirements-macos.txt
sudo .venv/bin/python server/depth_server.py
```

Build the app yourself: `tools/macos/build_macos_app.sh` (it explains what it
needs at the top). How the Mac version talks to the camera is described in
`docs/macos/camera-notes.md`.
