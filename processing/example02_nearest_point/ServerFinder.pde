// SPDX-License-Identifier: MIT
// ServerFinder.pde
//
// Finds the depth server's address, so you can write
//     String SERVER = "auto";
// at the top of your sketch instead of an IP address.
//
// You do not need to change anything in this tab. Every example has its own
// copy (all copies are the same).
//
// How it works:
//   1. The server says "I am here" on the network once per second (a small
//      message sent to every computer on the network). We listen for it and
//      use the address it came from.
//   2. Some networks (often shared or public Wi-Fi) block these messages. If we hear
//      nothing for 3 seconds, we try the name "realsense.local" instead.
//   3. If SERVER is not "auto" (for example "192.168.1.50" or
//      "my-computer.local"), we simply use what you wrote.

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import java.net.StandardSocketOptions;

public static class ServerFinder implements Runnable {

  // Must match discovery_port in the server's config.toml.
  static final int DISCOVERY_PORT = 8766;
  // The name we try when the announcements do not arrive.
  static final String FALLBACK_NAME = "realsense.local";
  // Every announcement from the server starts with this word.
  static final String ANNOUNCEMENT_WORD = "realsense-f200";

  String wanted;                    // what the sketch wrote in SERVER
  volatile String address = null;   // the address we found (null = not yet)

  ServerFinder(String server) {
    wanted = server.trim();
    if (wanted.equalsIgnoreCase("auto")) {
      // Listen in the background, so the sketch keeps running meanwhile.
      Thread listener = new Thread(this);
      listener.setDaemon(true);
      listener.start();
    } else {
      address = wanted;
    }
  }

  // The server's address, or null while we are still looking.
  String getAddress() {
    return address;
  }

  // Runs in the background when SERVER is "auto".
  public void run() {
    System.out.println("Looking for the depth server on the network ...");
    DatagramSocket socket = openListener();
    String lastFound = null;
    int triesWithoutLuck = 0;
    long lastHeardFromCurrent = 0;   // when the server we use last answered
    while (true) {
      String found = null;
      if (socket != null) {
        found = waitForAnnouncement(socket);
      } else {
        sleepSeconds(3);   // could not listen: only the name is left
      }
      if (found == null) {
        found = lookUpName(FALLBACK_NAME);
      }
      if (found != null) {
        long now = System.currentTimeMillis();
        // If there are two depth servers on the network, stay with the one
        // we already use, as long as it was heard in the last 10 seconds.
        boolean currentStillThere = address != null && now - lastHeardFromCurrent < 10000;
        if (found.equals(address) || !currentStillThere) {
          address = found;
          lastHeardFromCurrent = now;
          if (!found.equals(lastFound)) {
            System.out.println("Found the depth server at " + found);
            lastFound = found;
          }
        }
      } else if (address == null && ++triesWithoutLuck % 4 == 0) {
        // Remind the user every 12 seconds or so, not on every try.
        System.out.println("Still looking for the depth server ... (is it running? "
          + "If this goes on, write its address in SERVER, see the server's window)");
      }
    }
  }

  // Open a "mailbox" for the announcements. Several sketches on the same
  // computer can listen at the same time thanks to the "reuse" options.
  DatagramSocket openListener() {
    try {
      DatagramSocket socket = new DatagramSocket(null);
      socket.setReuseAddress(true);
      try {
        socket.setOption(StandardSocketOptions.SO_REUSEPORT, true);
      }
      catch (Exception notSupported) {
        // Some systems do not have this option. That is fine.
      }
      socket.bind(new InetSocketAddress(DISCOVERY_PORT));
      socket.setSoTimeout(3000);   // wait at most 3 seconds per try
      return socket;
    }
    catch (Exception problem) {
      System.out.println("Cannot listen for the server's announcements (" + problem.getMessage()
        + "). Trying the name " + FALLBACK_NAME + " instead.");
      return null;
    }
  }

  // Wait up to 3 seconds for an announcement. Returns the sender's
  // address, or null if none arrived.
  String waitForAnnouncement(DatagramSocket socket) {
    byte[] buffer = new byte[256];
    long giveUp = System.currentTimeMillis() + 3000;
    while (System.currentTimeMillis() < giveUp) {
      try {
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
        socket.receive(packet);
        String text = new String(packet.getData(), 0, packet.getLength(), "UTF-8");
        if (text.startsWith(ANNOUNCEMENT_WORD)) {
          return packet.getAddress().getHostAddress();
        }
        // Some other program's message on the same port: ignore it.
      }
      catch (SocketTimeoutException nothingArrived) {
        return null;
      }
      catch (Exception problem) {
        // Something unexpected went wrong with the network. Wait a moment,
        // so we do not retry hundreds of times per second.
        sleepSeconds(1);
        return null;
      }
    }
    return null;
  }

  // Turn a name like "realsense.local" into an address. We pick the
  // IPv4 address (like 192.168.1.50), which works most reliably.
  String lookUpName(String name) {
    try {
      for (InetAddress candidate : InetAddress.getAllByName(name)) {
        if (candidate instanceof Inet4Address) {
          return candidate.getHostAddress();
        }
      }
    }
    catch (Exception notFound) {
      // The name is unknown on this network.
    }
    return null;
  }

  static void sleepSeconds(int seconds) {
    try {
      Thread.sleep(seconds * 1000L);
    }
    catch (InterruptedException stop) {
    }
  }
}
