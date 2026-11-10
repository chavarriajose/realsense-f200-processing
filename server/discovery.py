# SPDX-License-Identifier: AGPL-3.0-or-later
"""
discovery.py

Lets sketches find the server by themselves, so you can write
    String SERVER = "auto";
instead of typing an IP address.

How it works: once per second the server sends a tiny message to every
computer on the local network (a "broadcast"). The message says:

    realsense-f200 8765 9000

which means "a RealSense depth server is here, images on port 8765, values
on port 9000". A sketch that waits for this message knows the server's
address from where the message came from.

Some networks (often shared or public Wi-Fi) block broadcasts. Then sketches fall back
to the name "realsense.local", or to an address typed by hand.
"""

import asyncio
import socket
import subprocess
import sys

# Every announcement starts with this word, so sketches can tell our message
# apart from other programs that might use the same port.
ANNOUNCEMENT_WORD = "realsense-f200"


def broadcast_addresses():
    """
    The "broadcast address" of every network this computer is connected to,
    for example 192.168.1.255. A message sent there reaches every computer
    on that network.

    On Linux we ask the 'ip' command, which prints lines like:
        2: wlp0s20f3    inet 192.168.1.50/24 brd 192.168.1.255 scope global ...
    and take the address after 'brd'.

    On macOS we ask 'ifconfig', which prints lines like:
        inet 192.168.1.50 netmask 0xffffff00 broadcast 192.168.1.255
    and take the address after 'broadcast'.

    Windows has no such command with a simple, language independent output,
    so there we use the general "everyone" address 255.255.255.255 (below).
    Windows sends it to the main network, which is the one that matters on
    a normal PC or laptop.
    """
    if sys.platform == "darwin":
        command, keyword = ["ifconfig"], "broadcast"
    else:
        command, keyword = ["ip", "-o", "-4", "addr", "show"], "brd"
    output = ""
    if sys.platform != "win32":
        try:
            output = subprocess.run(command, capture_output=True, text=True,
                                    timeout=2).stdout
        except (OSError, subprocess.TimeoutExpired):
            output = ""
    addresses = []
    for line in output.splitlines():
        words = line.split()
        if keyword in words:
            addresses.append(words[words.index(keyword) + 1])
    # If we found nothing, try the general "everyone" address.
    addresses = addresses or ["255.255.255.255"]

    if sys.platform in ("darwin", "win32"):
        # On a Mac or a Windows PC the camera is usually plugged into the
        # person's own computer, and the sketch runs on that same computer.
        # Announcing to 127.0.0.1 ("this computer") makes "auto" work even
        # without any network.
        addresses.append("127.0.0.1")
    return addresses


async def announce_forever(discovery_port, websocket_port, osc_port):
    """Send the announcement once per second, until the server stops."""
    message = f"{ANNOUNCEMENT_WORD} {websocket_port} {osc_port}".encode()

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sender.setblocking(False)

    seconds = 0
    targets = broadcast_addresses()
    try:
        while True:
            # Networks can change (Wi-Fi reconnects, cable plugged in), so we
            # look up the broadcast addresses again every 10 seconds.
            if seconds % 10 == 0:
                targets = broadcast_addresses()
            for target in targets:
                try:
                    sender.sendto(message, (target, discovery_port))
                except OSError:
                    pass  # this network is not reachable right now, try later
            seconds += 1
            await asyncio.sleep(1)
    finally:
        sender.close()


def local_name():
    """
    This computer's name on the local network, for example "realsense.local".
    Macs, Linux computers and recent Windows versions understand these
    ".local" names without any setup, as long as they are on the same network.
    """
    name = socket.gethostname()
    # On a Mac the name often already ends in ".local", so we add it only
    # when it is missing (otherwise we would print "name.local.local").
    if not name.endswith(".local"):
        name += ".local"
    return name
