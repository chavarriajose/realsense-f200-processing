# Contributing

Thank you for wanting to help. This project exists so that anyone with an
old RealSense F200 can use it again, and every improvement you share makes
that easier for the next person. You do not need to be a programmer to help.

## Report a problem, or share how it went

Open an [issue](https://github.com/chavarriajose/realsense-f200-processing/issues)
(you need a free GitHub account). It helps a lot to include:

- the **version**: the server prints it at start, for example
  `Depth server is running. (version 0.9.1 beta)`
- your **computer and system**: for example "Windows 11 laptop", "MacBook
  Air M2 with macOS 15", "Ubuntu 24.04 desktop PC"
- how the camera is **connected**: directly, or through which hub or adapter
- **what you did, what you expected and what happened**
- the **text in the server's window** (copy and paste it), and a screenshot
  if something looks wrong

"It worked on my computer" is useful too: the project is in beta, and
every report of a computer where it works tells others they can try.

## Share an improvement

Changed something that works better? Fixed a guide, found a clearer way to
say something, added an example, or got the camera working on another
computer? Please send it back.

**The easy way** (no git needed): open an issue, describe what you changed
and attach the changed files or paste the text.

**The usual way** (a "pull request"):

1. Click **Fork** on the project page. GitHub makes your own copy.
2. Change the files in your copy (GitHub's website has an edit button on
   every file, or use git on your computer).
3. Click **Contribute > Open pull request** and describe what you changed
   and how you tested it.

Small steps are welcome. One fix per pull request is easier to check than
many changes at once.

## What a change should look like

The people who use this project are artists, designers, makers and anyone
curious, many with little or no coding experience. So:

- **Code:** easy to read, with comments that explain *why*, not only what.
  Clear and simple beats clever and short.
- **Guides:** exact steps and commands, and what the person will see.
  Assume very little terminal experience. Write for anyone, not for a
  school or a class.
- **Test with a real camera** if your change touches the camera, the server
  or the examples, and say on which computer you tested.
- Keep everything that talks to the camera in the capture file of its
  system (`server/capture_linux.py`, `capture_macos.py`,
  `capture_windows.py`). The network messages, the examples and the guides
  are the same for every system.
- Please do not use the long dash character in texts; use commas,
  parentheses or two sentences instead. (A small house style rule that
  keeps the guides easy to read.)

Code written with the help of AI tools is welcome, as long as you have
tested it and you say so in the pull request, the same way this project
says so in its [README](README.md#how-this-was-made).

## License of your contribution

By sending a change, you agree that it is shared under the same license as
the part you changed: the AGPL-3.0 for the server, the tools and the guides,
the MIT license for the Processing examples (see the
[README](README.md#license)). That keeps the project open for everyone.
