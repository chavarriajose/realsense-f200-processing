# The camera on your own Windows PC

This guide is for plugging the RealSense F200 camera **directly into your
own Windows PC or laptop**, and running your sketches on that same
computer. You need no Linux computer for this, and you install **no camera
driver**: Windows already knows the camera.

(If the camera is connected to another computer on your network instead,
you only need Processing: go straight to [the first sketch guide](../first-sketch.md).)

## What you need

- The RealSense F200 camera (also sold by Creative as "VF0800").
- A **USB 3.0 port**. These are often blue inside, or marked "SS"
  (SuperSpeed). A USB 3.0 hub or a USB-C to USB-A adapter works fine too.
  With a USB 2.0 port or hub the camera does not work.
- Windows 10 or Windows 11, 64-bit, on a normal Intel or AMD processor.
  (Windows on ARM, for example Snapdragon laptops, is not supported.)
- Processing 4 (see [the first sketch guide](../first-sketch.md)).

You do **not** need administrator rights for the depth server.

## 1. Plug in the camera

Plug the camera into a USB 3.0 port and wait a few seconds. Windows sets it
up by itself. To check: right-click the Start button, choose
**Device Manager**, and open **Cameras**. You should see:

- Intel(R) RealSense(TM) 3D Camera (Front F200) **Depth**
- Intel(R) RealSense(TM) 3D Camera (Front F200) **RGB**

(You may also see a "Creative VF0800" sound device: those are the camera's
microphones. The server does not use them.)

## 2. Get the program

1. Download `RealSense-Depth-Server-Windows.zip` from the project's
   **Releases** page on GitHub (right side of the project page).
2. In your Downloads folder, right-click the zip file and choose
   **Extract All...**, then **Extract**. You get a folder called
   **RealSense-Depth-Server-Windows**. Inside it is the folder
   **RealSense Depth Server**.
3. Move that folder wherever you like, for example to your Documents.
   Keep everything inside it together: the program needs the `_internal`
   folder next to it.

## 3. Start it the first time

1. Open the **RealSense Depth Server** folder and double-click
   **RealSense Depth Server** (the one whose type is "Application", not
   READ ME FIRST or LICENSE).
2. The first time, Windows shows a blue box: **"Windows protected your PC"**.
   This happens because the program is free and not signed with a paid
   certificate (that costs money every year). Click **More info**, then
   **Run anyway**. You only do this once.
3. A black window opens. After a few lines of settings you see something
   like this:

   ```
   ================================================================
     Depth server is running.

     What to write at the top of a sketch:
       String SERVER = "auto";        (finds this server by itself)
     If "auto" does not work on your network, use one of these:
       String SERVER = "my-laptop.local";
       String SERVER = "192.168.1.50";

     Images: WebSocket port 8765, values: OSC port 9000
     To stop the server, close this window or press Ctrl+C.
   ================================================================

   Camera ready.
   ```

   (The name and the number are only examples: your computer shows its own.)

4. Windows may ask **"Windows Defender Firewall has blocked some features of
   this app"** for RealSense Depth Server. Tick **Private networks** and
   click **Allow access** if sketches on *other* computers should use your
   camera too. Sketches on your own computer work either way, so you can
   also click **Cancel**. (Allowing may ask for an administrator password.)

Leave the black window open while you work. It is the server.

(Tip for later downloads: if you right-click the zip file, choose
**Properties** and tick **Unblock** at the bottom *before* extracting it,
the blue "Windows protected your PC" box does not appear at all.)

## 4. Stop the server

Close the black window, or click into it and press **Ctrl+C**.

Either way the server lets go of the camera, and other programs (like the
Windows Camera app) can use it again.

### Change settings

The settings are in the file `config.toml` inside the `_internal` folder
(next to RealSense Depth Server). For example, the infrared and color
images are switched off at first; to send them, change `ir = false` and
`color = false` to `true`. Open the file with Notepad (right-click,
**Open with**, **Notepad**), change it, save, and start the server again.
Every setting has a short explanation in the file.

## 5. Run a sketch

Follow [the first sketch guide](../first-sketch.md): install Processing, get
the examples and press Run. Two things to know on Windows:

- With the camera on your own computer, `String SERVER = "auto";` finds the
  server by itself. If it does not, write `String SERVER = "127.0.0.1";`
  (`127.0.0.1` always means "this computer").
- If Windows asks about **"OpenJDK Platform binary"** (that is Processing) in
  a firewall box, click **Allow access**. "auto" and example 05 need it to
  hear the server.

## If it does not work

| What you see | What to try |
|--------------|-------------|
| `Camera not available: Could not find the RealSense F200 camera` (repeating every 3 seconds) | Check the cable and the port, and look in Device Manager (step 1). If the camera is not listed, try another USB 3.0 port or hub. The server starts by itself as soon as the camera appears. |
| `Camera not available: The camera is busy` | Another program is using the camera: the Windows Camera app, a video call, the preview tool, or a second copy of the server. Close it; the server then starts by itself. |
| `Windows does not allow this program to use the camera` | Open **Settings > Privacy & security > Camera** and switch on **Camera access** and **Let desktop apps access your camera**. |
| `Could not start the server: [WinError 10048] ...` and `Press Enter to close this window.` | The server is already running in another window. Use that one, or close it first. |
| The window says `Press Enter to close this window.` right away | Read the lines above it, they say why. |
| `Lost the camera` followed by `Camera ready.` | A short USB hiccup. The server recovered by itself. If it happens often, try another port or hub. |
| The sketch stays at `Looking for the depth server ...` | Check that the black server window is open and says `Camera ready.` Then write `"127.0.0.1"` (same computer) or the server's address instead of "auto". |
| Example 05 says `Waiting for values` | Allow Processing in the firewall box (step 5). If you clicked Cancel there, open **Windows Security > Firewall & network protection > Allow an app through firewall**, click **Change settings** and tick **OpenJDK Platform binary**, or use `"127.0.0.1"` instead of "auto". Only one sketch per computer can use port 12000: close other copies of example 05. |
| `The package "oscP5" does not exist` | Install oscP5, see [the first sketch guide](../first-sketch.md), step 6. |
| The image is mostly black | The camera only measures between about 20 cm and 1.2 m. Move closer. |
| The Windows sign-in screen with face recognition (Windows Hello) | If Windows Hello uses this camera, it may hold it while the sign-in screen is shown. The server says the camera is busy and starts as soon as Windows lets go. |

## For developers

Run the server from a terminal instead of the program. You need 64-bit
Python 3.11 or newer from https://www.python.org/downloads/windows/ . In
PowerShell, from the main project folder:

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements-windows.txt
.venv\Scripts\python server\depth_server.py
```

The live camera preview: `.venv\Scripts\python tools\preview.py`.

Build the program yourself:

```
powershell -ExecutionPolicy Bypass -File tools\windows\build_windows_exe.ps1
```

It explains what it needs at the top, and puts the result in `dist\`. How
the Windows version talks to the camera is described in
`docs/windows/camera-notes.md`.
