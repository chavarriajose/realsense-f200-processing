# SPDX-License-Identifier: AGPL-3.0-or-later
r"""
depth_server.py

The depth server. It reads the RealSense F200 camera and sends what it sees
to sketches on the network:

  * images over WebSocket (port 8765 by default):
        depth8   grayscale depth picture, ready to show
        depth16  exact distance in millimeters for every pixel
        ir       infrared picture
        color    color picture
    plus "values" (the same numbers as OSC, as JSON text, handy for p5.js)

  * simple values over OSC (the sketch says hello on port 9000 by default):
        /nearest x y mm        the closest point
        /presence 0|1          is something there?
        /blob x y mm size      the biggest object
        /average mm            average distance

How to start it (from the main project folder):

    .venv/bin/python server/depth_server.py          (Linux, macOS with sudo)
    .venv\Scripts\python server\depth_server.py      (Windows)

The exact message formats are described in docs/protocol.md.
All settings are in server/config.toml.
"""

import asyncio
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import time
import tomllib
import zlib

import cv2
import websockets
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

# Everything that talks to the camera is in capture_linux.py (Linux),
# capture_macos.py (macOS) or capture_windows.py (Windows). capture.py picks
# the right one for us.
from capture import F200Camera
import discovery
import processing_steps as steps


# The version of the project. It is printed at start, so people can say
# which version they use when they report a problem. Change it for every
# release (and in CHANGELOG.md).
VERSION = "0.9.1 beta"

SERVER_FOLDER = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SERVER_FOLDER, "config.toml")

# Every image message starts with a number that says which image it is.
STREAM_IDS = {"depth8": 1, "depth16": 2, "ir": 3, "color": 4}
IMAGE_STREAMS = list(STREAM_IDS.keys())

# The second byte says how the image bytes are packed.
ENCODING_RAW = 0    # plain bytes, nothing to unpack
ENCODING_ZLIB = 1   # squeezed with zlib, unpack with an "Inflater"
ENCODING_JPEG = 2   # a JPEG file (used for color)

# When a sketch does not say which OSC port it listens on, we use this one.
DEFAULT_OSC_REPLY_PORT = 12000


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def load_config(path):
    """Read config.toml and return it as a dictionary of sections."""
    with open(path, "rb") as config_file:
        return tomllib.load(config_file)


def print_config(config):
    """Show the settings in use, so it is easy to check them at start."""
    print("Settings from config.toml:")
    for section, values in config.items():
        line = ", ".join(f"{key}={value}" for key, value in values.items())
        print(f"  [{section}] {line}")


def my_ip_addresses():
    """
    The IP addresses of this computer, so people know what to type in
    their sketch.
    """
    if sys.platform.startswith("linux"):
        # On Linux, 'hostname -I' prints them all, separated by spaces.
        try:
            output = subprocess.run(["hostname", "-I"], capture_output=True,
                                    text=True, timeout=2).stdout
            # Skip IPv6 addresses (they contain ':'), sketches need the IPv4 one.
            return [address for address in output.split() if ":" not in address]
        except (OSError, subprocess.TimeoutExpired):
            return []

    # macOS and Windows have no 'hostname -I'. Instead we ask the system which address it
    # would use to reach the internet. Nothing is actually sent: "connecting"
    # a UDP socket only picks the route. 192.0.2.1 is a documentation
    # address that is never used by a real computer.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
        return [] if address.startswith("0.") else [address]
    except OSError:
        return []   # no network at all


# ---------------------------------------------------------------------------
# Building the messages
# ---------------------------------------------------------------------------

def image_message(stream, encoding, width, height, payload):
    """
    One binary WebSocket message: an 8 byte header, then the image bytes.

        byte 0      stream id (1 = depth8, 2 = depth16, 3 = ir, 4 = color)
        byte 1      encoding  (0 = raw, 1 = zlib, 2 = jpeg)
        bytes 2-3   width     (big endian, 16 bit)
        bytes 4-5   height    (big endian, 16 bit)
        bytes 6-7   reserved, always 0

    Big endian is the byte order Java (and so Processing) reads by default.
    """
    header = struct.pack(">BBHHH", STREAM_IDS[stream], encoding, width, height, 0)
    return header + payload


def build_messages(frames, wanted, config):
    """
    Turn one set of camera frames into ready-to-send messages, but only for
    the streams that at least one sketch wants (no work for nobody).
    Returns a dictionary: stream name -> message.
    """
    near = config["range"]["near_mm"]
    far = config["range"]["far_mm"]
    compress = config["network"]["compress"]
    height, width = frames.depth_mm.shape
    messages = {}

    def pack(raw_bytes):
        # zlib level 1 is the fastest setting and already shrinks depth a lot.
        if compress:
            return ENCODING_ZLIB, zlib.compress(raw_bytes, 1)
        return ENCODING_RAW, raw_bytes

    if "depth8" in wanted:
        gray = steps.make_depth8(frames.depth_mm, near, far)
        encoding, payload = pack(gray.tobytes())
        messages["depth8"] = image_message("depth8", encoding, width, height, payload)

    if "depth16" in wanted:
        # ">u2" means: unsigned 16 bit, big endian byte order.
        big_endian = frames.depth_mm.astype(">u2").tobytes()
        encoding, payload = pack(big_endian)
        messages["depth16"] = image_message("depth16", encoding, width, height, payload)

    if "ir" in wanted and frames.ir is not None:
        encoding, payload = pack(frames.ir.tobytes())
        messages["ir"] = image_message("ir", encoding, width, height, payload)

    if "color" in wanted and frames.color is not None:
        # Photos are much smaller as JPEG, and every platform can read JPEG.
        ok, jpeg = cv2.imencode(".jpg", frames.color, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            color_height, color_width = frames.color.shape[:2]
            messages["color"] = image_message("color", ENCODING_JPEG,
                                              color_width, color_height, jpeg.tobytes())
    return messages


# ---------------------------------------------------------------------------
# WebSocket clients (sketches that want images)
# ---------------------------------------------------------------------------

class WebSocketClient:
    """What we remember about one connected sketch."""

    def __init__(self, websocket):
        self.websocket = websocket
        self.streams = set()   # which streams this sketch asked for
        self.busy = False      # True while we are still sending to it


class DepthServer:
    def __init__(self, config):
        self.config = config
        self.allowed_streams = {name for name in IMAGE_STREAMS
                                if config["streams"].get(name, False)}
        self.allowed_streams.add("values")  # values are small, always allowed
        self.clients = {}       # websocket -> WebSocketClient
        self.osc_subscribers = {}  # (ip, port) -> time of the last hello
        self.osc_senders = {}      # (ip, port) -> SimpleUDPClient
        self.camera = None
        # Running "send" tasks. Python only keeps a weak reference to tasks,
        # so we keep them here until they are finished.
        self.send_tasks = set()

    # ----- WebSocket -------------------------------------------------------

    async def handle_websocket(self, websocket, path=None):
        """Runs once for every sketch that connects, until it disconnects."""
        client = WebSocketClient(websocket)
        self.clients[websocket] = client
        address = websocket.remote_address[0]
        print(f"Sketch connected from {address} ({len(self.clients)} connected)")
        try:
            # The sketch tells us what it wants with a small JSON text, like
            #   {"streams": ["depth8", "values"]}
            # It can send a new one at any time to change its mind.
            async for message in websocket:
                if isinstance(message, str):
                    self.handle_request(client, message, address)
        except websockets.ConnectionClosed:
            pass
        finally:
            del self.clients[websocket]
            print(f"Sketch from {address} disconnected ({len(self.clients)} connected)")

    def handle_request(self, client, text, address):
        try:
            request = json.loads(text)
        except ValueError:
            request = None
        # We expect {"streams": [ ...names... ]}. Anything else is ignored
        # with one clear message, so a typo in a sketch is easy to find.
        streams = request.get("streams") if isinstance(request, dict) else None
        if not isinstance(streams, list) or not all(isinstance(n, str) for n in streams):
            print(f'Ignored a request from {address}. Expected something like '
                  f'{{"streams": ["depth8"]}}, got: {text[:80]}')
            return
        asked = set(streams)
        client.streams = asked & self.allowed_streams
        refused = asked - self.allowed_streams
        print(f"  {address} wants: {', '.join(sorted(client.streams)) or 'nothing'}")
        if refused:
            print(f"  (not sent, switched off in config.toml or unknown: "
                  f"{', '.join(sorted(refused))})")

    async def send_to_client(self, client, messages):
        """Send a list of messages to one sketch."""
        client.busy = True
        try:
            for message in messages:
                await client.websocket.send(message)
        except websockets.ConnectionClosed:
            pass  # handle_websocket notices and cleans up
        except Exception as problem:
            print(f"Could not send to a sketch: {problem}")
        finally:
            client.busy = False

    def send_to_all_clients(self, messages, values):
        for client in list(self.clients.values()):
            if client.busy:
                # This sketch has not received the last frame yet (slow
                # network). Skip this frame instead of piling up old ones,
                # so the sketch always gets fresh images.
                continue
            outgoing = [messages[name] for name in sorted(client.streams)
                        if name in messages]
            if "values" in client.streams:
                outgoing.append(json.dumps(values))
            if outgoing:
                task = asyncio.create_task(self.send_to_client(client, outgoing))
                self.send_tasks.add(task)
                task.add_done_callback(self.send_tasks.discard)

    # ----- OSC -------------------------------------------------------------

    def reply_port(self, ip, args):
        """
        The port a sketch wants its values on: the first argument of its
        /subscribe message, or 12000 if it did not give one. Returns None
        (and prints why) if the argument is not a usable port number, so a
        single strange message can never crash the server.
        """
        if not args:
            return DEFAULT_OSC_REPLY_PORT
        port = args[0]
        # (In Python, True and False also count as int, so we exclude them.)
        if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535:
            return port
        print(f"OSC: ignored a message from {ip}: the port must be a whole "
              f"number between 1 and 65535, got {port!r}")
        return None

    def handle_osc_subscribe(self, client_address, osc_address, *args):
        """
        A sketch says hello: "/subscribe" with the port it listens on.
        We remember its IP address and port, and send values there until it
        stops saying hello for `subscription_timeout` seconds.
        """
        ip = client_address[0]
        port = self.reply_port(ip, args)
        if port is None:
            return
        key = (ip, port)
        if key not in self.osc_subscribers:
            print(f"OSC: sending values to {ip}:{port}")
            self.osc_senders[key] = SimpleUDPClient(ip, port)
        self.osc_subscribers[key] = time.time()

    def handle_osc_unsubscribe(self, client_address, osc_address, *args):
        ip = client_address[0]
        port = self.reply_port(ip, args)
        if self.osc_subscribers.pop((ip, port), None) is not None:
            self.osc_senders.pop((ip, port), None)
            print(f"OSC: {ip}:{port} said goodbye")

    def send_osc_values(self, values):
        timeout = self.config["values"]["subscription_timeout"]
        now = time.time()
        for key, last_hello in list(self.osc_subscribers.items()):
            if now - last_hello > timeout:
                print(f"OSC: {key[0]}:{key[1]} stopped sending /subscribe, not sending anymore")
                del self.osc_subscribers[key]
                del self.osc_senders[key]
                continue
            sender = self.osc_senders[key]
            try:
                for name, numbers in values.items():
                    sender.send_message("/" + name, numbers)
            except (OSError, OverflowError):
                pass  # network hiccup: try again with the next frame

    # ----- Camera loop -----------------------------------------------------

    def open_camera(self):
        camera_settings = self.config["camera"]
        return F200Camera(width=camera_settings["width"],
                          height=camera_settings["height"],
                          fps=camera_settings["fps"],
                          want_ir="ir" in self.allowed_streams,
                          want_color="color" in self.allowed_streams)

    async def camera_loop(self):
        """Read the camera and send everything, send_fps times per second."""
        loop = asyncio.get_running_loop()
        seconds_per_frame = 1.0 / self.config["network"]["send_fps"]
        near = self.config["range"]["near_mm"]
        far = self.config["range"]["far_mm"]
        min_pixels = self.config["values"]["min_pixels"]
        next_send = time.time()   # when the next frame should go out

        while True:
            # (Re)open the camera if needed, for example after it was unplugged.
            if self.camera is None:
                try:
                    self.camera = await loop.run_in_executor(None, self.open_camera)
                    print("Camera ready.")
                except (RuntimeError, OSError, cv2.error) as problem:
                    # OSError and cv2.error can happen while the camera is
                    # being unplugged or plugged in. We just try again.
                    print(f"Camera not available: {problem}\nTrying again in 3 seconds...")
                    await asyncio.sleep(3)
                    continue

            try:
                # camera.read() waits for the camera, so we run it in a helper
                # thread. Meanwhile the server keeps talking to the sketches.
                frames = await loop.run_in_executor(None, self.camera.read)
            except (RuntimeError, OSError, cv2.error) as problem:
                print(f"Lost the camera: {problem}")
                try:
                    await loop.run_in_executor(None, self.camera.close)
                except Exception:
                    pass  # it is already broken, we only tidy up
                self.camera = None
                continue

            # Only do the work that somebody needs.
            wanted = set()
            for client in self.clients.values():
                wanted |= client.streams
            if self.clients or self.osc_subscribers:
                values = steps.compute_values(frames.depth_mm, near, far, min_pixels)
                messages = build_messages(frames, wanted, self.config)
                self.send_to_all_clients(messages, values)
                self.send_osc_values(values)

            # Wait until it is time for the next frame. We aim at fixed
            # moments (every seconds_per_frame) instead of "wait a bit after
            # each frame": the system often wakes us a few milliseconds late
            # (on Windows up to 16 ms), and this way the next wait is simply
            # a little shorter, so we still send send_fps frames per second.
            next_send += seconds_per_frame
            now = time.time()
            if next_send < now - seconds_per_frame:
                next_send = now   # we fell far behind: start counting afresh
            await asyncio.sleep(max(0.0, next_send - now))

    # ----- Start everything --------------------------------------------------

    def print_how_to_connect(self, announcing):
        """Tell the person starting the server what to write in sketches."""
        network = self.config["network"]
        line = "=" * 64
        print()
        print(line)
        print(f"  Depth server is running. (version {VERSION})")
        print()
        print("  What to write at the top of a sketch:")
        if announcing:
            print('    String SERVER = "auto";        (finds this server by itself)')
            print("  If \"auto\" does not work on your network, use one of these:")
        print(f'    String SERVER = "{discovery.local_name()}";')
        for address in my_ip_addresses():
            print(f'    String SERVER = "{address}";')
        print()
        print(f"  Images: WebSocket port {network['websocket_port']}, "
              f"values: OSC port {network['osc_port']}")
        print("  To stop the server, close this window or press Ctrl+C.")
        print(line)
        print()

    async def run(self):
        network = self.config["network"]
        loop = asyncio.get_running_loop()

        # Stop nicely when we get Ctrl+C (SIGINT), when the system asks the
        # service to stop (SIGTERM, used by systemd) or when the window is
        # closed (SIGHUP): cancel the main task,
        # which runs the "finally" part below and releases the camera.
        main_task = asyncio.current_task()
        if sys.platform == "win32":
            # Windows works differently: asyncio.run() already turns Ctrl+C
            # into "cancel the main task" by itself. We only add Ctrl+Break.
            # Closing the console window also arrives here as SIGBREAK, but
            # Windows ends the program a moment later, before Python can run
            # this handler. That is fine: when a program ends, Windows
            # releases the camera on its own (tested). So there is no need
            # to try harder for a "clean" stop in that case.
            signal.signal(signal.SIGBREAK,
                          lambda *_: loop.call_soon_threadsafe(main_task.cancel))
        else:
            # SIGHUP is what a terminal sends when its window is closed.
            for stop_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                loop.add_signal_handler(stop_signal, main_task.cancel)

        dispatcher = Dispatcher()
        dispatcher.map("/subscribe", self.handle_osc_subscribe, needs_reply_address=True)
        dispatcher.map("/unsubscribe", self.handle_osc_unsubscribe, needs_reply_address=True)
        osc_server = AsyncIOOSCUDPServer(("0.0.0.0", network["osc_port"]), dispatcher, loop)
        try:
            osc_transport, _ = await osc_server.create_serve_endpoint()
            # max_size: sketches only send tiny JSON messages to us.
            # compression=None: images are already compressed by us.
            websocket_server = await websockets.serve(
                self.handle_websocket, "0.0.0.0", network["websocket_port"],
                max_size=64 * 1024, compression=None)
        except OSError as problem:
            # Usually: "Address already in use".
            print(f"\nCould not start the server: {problem}")
            print("Is the depth server already running (in another window, or as a service)?")
            print("Or change websocket_port / osc_port in config.toml.")
            return 1  # exit code 1 tells systemd that starting failed

        # Announce ourselves on the network, so sketches with
        # SERVER = "auto" can find us (see discovery.py).
        announcer = None
        if network.get("discovery", True):
            announcer = asyncio.create_task(discovery.announce_forever(
                network.get("discovery_port", 8766),
                network["websocket_port"], network["osc_port"]))

        try:
            self.print_how_to_connect(announcer is not None)
            await self.camera_loop()
        except asyncio.CancelledError:
            pass  # we were asked to stop
        finally:
            if announcer is not None:
                announcer.cancel()
            websocket_server.close()
            osc_transport.close()
            if self.camera is not None:
                self.camera.close()
            print("\nServer stopped.")


def main():
    # Show every message right away, also when the output goes to a file or
    # a log (for example the systemd service or an automatic test). Python
    # would otherwise keep messages in memory for a while, and they would be
    # lost if the program is stopped hard.
    sys.stdout.reconfigure(line_buffering=True)

    # On a Mac the camera needs administrator rights (see capture_macos.py).
    # Without them, trying again every few seconds would never help, so we
    # explain it once and stop.
    if sys.platform == "darwin" and os.geteuid() != 0:
        print("On a Mac the depth server needs administrator rights to use the camera.")
        if getattr(sys, "frozen", False):
            # We are running inside the Mac app (see tools/macos/build_macos_app.sh).
            print("Please start it by opening the RealSense Depth Server app.")
        else:
            print("Start it with sudo in front:")
            print("    sudo .venv/bin/python server/depth_server.py")
            print("or use the RealSense Depth Server app, which asks for your password.")
        sys.exit(1)

    config_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    config = load_config(config_path)
    print_config(config)
    exit_code = asyncio.run(DepthServer(config).run())
    if exit_code:
        keep_window_open()
    sys.exit(exit_code or 0)


def keep_window_open():
    """
    On Windows, people start the server by double-clicking the .exe (see
    tools/windows/build_windows_exe.ps1). If the server stops because of a problem,
    Windows would close its window at once, and nobody could read why. So in
    that case we wait for Enter first. From a terminal this is not needed.
    """
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            input("\nPress Enter to close this window.")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # An unexpected error (for example a typo in config.toml): show the
        # full report, and on Windows keep the window open so it can be read.
        import traceback
        traceback.print_exc()
        keep_window_open()
        sys.exit(1)
