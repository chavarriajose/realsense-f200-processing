# Your first depth sketch

This guide gets you from nothing to a depth image in Processing. It works
the same on a Mac, a Windows PC or a Linux computer. You only need
Processing: no drivers, nothing else to install.

Before you start, the **depth server** must be running on the computer the
camera is plugged into:

- camera on a Linux computer: [linux/setup.md](linux/setup.md)
- camera on your own Mac: [macos/setup.md](macos/setup.md)
- camera on your own Windows PC: [windows/setup.md](windows/setup.md)

That can be the same computer you write sketches on, or another computer on
the same network. Usually the sketch finds the server by itself. Just in
case, look at the server's window (or ask whoever runs it) for **the
server's address**, which looks like `realsense.local` or `192.168.1.50`.

## 1. Install Processing

Go to https://processing.org/download and download Processing 4 for your
system:

- **Mac:** choose "Apple Silicon" for Macs with an M1 chip or newer, "Intel"
  for older ones. Open the downloaded file, drag **Processing** into your
  **Applications** folder and open it from there. If macOS asks whether you
  are sure, click **Open**.
- **Windows:** install or unzip it as the download page explains, then start
  **Processing**.
- **Linux:** follow the instructions on the download page.

## 2. Get the examples

Download the project (on its GitHub page: green **Code** button, then
**Download ZIP**) and unzip it. The examples are in the `processing` folder.

## 3. Open the first example

In the `processing` folder, open `example01_show_depth` and double-click
`example01_show_depth.pde`. Processing opens the sketch. You will see three
tabs at the top: `example01_show_depth`, `DepthClient` and `ServerFinder`.
You only work in the first one. `DepthClient` receives the images from the
server, and `ServerFinder` finds the server on the network for you.

## 4. The server's address

Near the top of the sketch you find this line:

```java
String SERVER = "auto";
```

Leave it like this. "auto" means the sketch looks for the depth server on
the network by itself. Only if that does not work (see step 5), replace
`auto` with the server's address, for example:

```java
String SERVER = "realsense.local";
```

Keep the quotes and the semicolon. If the server runs on the same computer
as the sketch, the address is always `"127.0.0.1"` ("this computer").

## 5. Run it

Press the **Run** button (the round button with the triangle).

A window opens. For a moment it says `Looking for the depth server (auto) ...`,
then the depth image appears: things close to the camera are bright, things
further away are darker, and places the camera cannot measure are black.
Move your hand in front of the camera and watch it change.

Your computer may ask whether Processing may use the network. Allow it:
"auto" needs this to hear the server, and example 05 needs it to receive
values.

- **Mac:** *"Do you want the application java to accept incoming network
  connections?"*: click **Allow**.
- **Windows:** a firewall box about **"OpenJDK Platform binary"** (that is
  Processing): click **Allow access**.

If it keeps saying `Looking for the depth server` for more than about 10
seconds, your network probably blocks the server's "I am here" message.
Write the server's address in `SERVER` (step 4) and run again.

## 6. Try the other examples

| Example                   | What it does                                     |
|---------------------------|--------------------------------------------------|
| `example02_nearest_point` | a circle follows the closest thing (your hand)   |
| `example03_threshold`     | only shows what is between two distances. Arrow keys change them. |
| `example04_point_cloud`   | the depth as 3D dots. Drag with the mouse to turn it. |
| `example05_osc_values`    | numbers only: nearest point, presence, blob, average |

They also start with `String SERVER = "auto";`. If you had to type an
address in step 4, do the same in each one.

**Example 05 needs the oscP5 library.** Install it once:

1. In Processing: **Sketch > Import Library > Manage Libraries...**
2. Search for `oscP5`, select it and click **Install**.

If the install fails, download `oscP5-0.9.9.zip` from
https://github.com/sojamo/oscp5/releases, unzip it, and move the `oscP5`
folder into the `libraries` folder of your Processing sketchbook
(`Documents/Processing/libraries` on Mac and Windows; create the `libraries`
folder if it does not exist). Then restart Processing.

## 7. Make your own

The easiest start: copy a whole example folder, rename the folder and the
`.pde` file inside it to the same new name (letters first, no spaces, for
example `my_depth_sketch`), and change it. Keep the `DepthClient` and
`ServerFinder` tabs: they do the connecting. [processing/README.md](../processing/README.md)
lists everything the `DepthClient` tab gives you, such as
`camera.depthImage` and `camera.getDistance(x, y)`.

The examples are under the MIT license, so you can use them freely in your
own sketches and artworks.

## If it does not work

| What you see | What to try |
|--------------|-------------|
| Stays at `Looking for the depth server ...` | Check that the server is running and says `Camera ready.` Make sure your computer is on the same network as the server. Then write the server's address instead of "auto" (step 4). |
| The console says `Could not connect to the depth server` | Same as above. The sketch keeps trying every 2 seconds, so you can fix the problem without stopping it. |
| Example 05 says `Waiting for values` | Allow Processing to use the network (step 5). On a Mac, check System Settings > Network > Firewall; on Windows, Windows Security > Firewall & network protection > Allow an app through firewall (tick **OpenJDK Platform binary**). Only one sketch per computer can use port 12000: close other copies of example 05. |
| `The package "oscP5" does not exist` | Install oscP5 (step 6). |
| The image is mostly black | The camera only measures between about 20 cm and 1.2 m. Move closer. |
