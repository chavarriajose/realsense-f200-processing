# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_client.py

A small test program that connects to the depth server like a sketch would,
receives images and values, and saves what it got as PNG files. Use it to
check the server without Processing.

How to run it (from the main project folder, while the server is running):

    .venv/bin/python tools/test_client.py 127.0.0.1 depth8 depth16 values

Replace 127.0.0.1 with the server's IP address when you run it on another
computer. After the address, list the streams you want:
    depth8  depth16  ir  color  values  osc

It uses the default ports (WebSocket 8765, OSC 9000, and 12000 to receive
OSC values). If you changed the ports in server/config.toml, change them in
main() below too.

It runs for 5 seconds, then prints how many messages arrived for each stream
and saves the last image of each stream as test_<stream>.png
(add --out <folder> to choose where).
"""

import asyncio
import json
import os
import socket
import struct
import sys
import threading
import time
import zlib

import cv2
import numpy as np
import websockets

STREAM_NAMES = {1: "depth8", 2: "depth16", 3: "ir", 4: "color"}
RUN_SECONDS = 5


def decode_image(message):
    """Undo what the server did: read the header, unpack the pixels."""
    stream_id, encoding, width, height, _ = struct.unpack(">BBHHH", message[:8])
    payload = message[8:]
    name = STREAM_NAMES[stream_id]
    if encoding == 2:  # JPEG
        return name, cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
    if encoding == 1:  # zlib
        payload = zlib.decompress(payload)
    if name == "depth16":
        return name, np.frombuffer(payload, ">u2").reshape(height, width).astype(np.uint16)
    return name, np.frombuffer(payload, np.uint8).reshape(height, width)


def listen_osc(server_ip, server_port, reply_port, results, stop):
    """Say hello to the server over OSC and collect the values it sends back."""
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import BlockingOSCUDPServer
    from pythonosc.udp_client import SimpleUDPClient

    dispatcher = Dispatcher()
    dispatcher.set_default_handler(lambda address, *args: results.append((address, args)))
    server = BlockingOSCUDPServer(("0.0.0.0", reply_port), dispatcher)
    server.timeout = 0.2
    SimpleUDPClient(server_ip, server_port).send_message("/subscribe", reply_port)
    while not stop.is_set():
        server.handle_request()
    SimpleUDPClient(server_ip, server_port).send_message("/unsubscribe", reply_port)
    server.server_close()


async def main():
    args = sys.argv[1:]
    out_folder = "."
    if "--out" in args:
        out_folder = args[args.index("--out") + 1]
        args = args[:args.index("--out")]
    server_ip, wanted = args[0], args[1:]

    osc_results, stop = [], threading.Event()
    osc_thread = None
    if "osc" in wanted:
        osc_thread = threading.Thread(target=listen_osc,
                                      args=(server_ip, 9000, 12000, osc_results, stop))
        osc_thread.start()

    counts, last_images, last_values = {}, {}, None
    websocket_streams = [w for w in wanted if w != "osc"]
    if websocket_streams:
        async with websockets.connect(f"ws://{server_ip}:8765", max_size=None) as ws:
            await ws.send(json.dumps({"streams": websocket_streams}))
            end = time.time() + RUN_SECONDS
            while time.time() < end:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1)
                except asyncio.TimeoutError:
                    continue
                if isinstance(message, str):
                    counts["values"] = counts.get("values", 0) + 1
                    last_values = json.loads(message)
                else:
                    name, image = decode_image(message)
                    counts[name] = counts.get(name, 0) + 1
                    last_images[name] = (image, len(message))
    else:
        time.sleep(RUN_SECONDS)

    stop.set()
    if osc_thread:
        osc_thread.join()

    for name, count in counts.items():
        print(f"{name}: {count} messages ({count / RUN_SECONDS:.1f} per second)")
    for name, (image, size) in last_images.items():
        path = os.path.join(out_folder, f"test_{name}.png")
        if name == "depth16":
            valid = image[image > 0]
            print(f"depth16: {image.shape}, median {np.median(valid):.0f} mm, "
                  f"{100 * valid.size / image.size:.0f} % with depth, {size} bytes")
            # Save a viewable version: 200..1200 mm -> bright..dark, 0 stays black.
            view = np.clip(255 - (image.astype(float) - 200) / 1000 * 255, 0, 255)
            view[image == 0] = 0
            cv2.imwrite(path, view.astype(np.uint8))
        else:
            print(f"{name}: {image.shape}, {size} bytes per message")
            cv2.imwrite(path, image)
        print("  saved", path)
    if last_values:
        print("values (WebSocket):", last_values)
    if osc_thread:
        print(f"osc: {len(osc_results)} messages")
        latest = {}
        for address, values in osc_results:
            latest[address] = values
        for address, values in sorted(latest.items()):
            print(f"  {address} {list(values)}")


if __name__ == "__main__":
    asyncio.run(main())
