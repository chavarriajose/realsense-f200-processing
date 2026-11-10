# SPDX-License-Identifier: AGPL-3.0-or-later
"""
collect_licenses.py

Used by the build scripts of the ready-made programs
(tools/windows/build_windows_exe.ps1 and tools/macos/build_macos_app.sh).
It copies the license texts of everything the program contains into one
folder, so they travel with it, as open source licenses ask:

  licenses/python/              Python itself (this file also covers the
                                parts Python brings along, like OpenSSL)
  licenses/<package>/           every Python package in the program
  licenses/libusb/              the libusb library (Mac app only)

Usage (the build scripts do this for you), with the Python of the build
environment, so it sees the same packages that go into the program:

    python tools/collect_licenses.py <target folder> [package ...]

Without a package list it uses the Windows list below.
"""

import shutil
import sys
from importlib import metadata
from pathlib import Path

# The packages inside the Windows program (see build_windows_exe.ps1).
# PyInstaller is listed because its small start-up program is included too.
# The Mac build adds "libusb1" (see build_macos_app.sh).
DEFAULT_PACKAGES = ["numpy", "opencv-python-headless", "websockets", "python-osc", "pyinstaller"]

# File names that hold license texts start with one of these words.
LICENSE_WORDS = ("LICENSE", "LICENCE", "COPYING", "NOTICE")

# The libusb C library is not a Python package, so its license is not on
# record anywhere pip can see. This short note says where to find it.
LIBUSB_NOTE = """libusb (the C library that talks to USB devices, used by the Mac app)
License: GNU Lesser General Public License, version 2.1 or later (LGPL-2.1-or-later)
Website: https://libusb.info
Source code and full license text: https://github.com/libusb/libusb
The copy in the Mac app comes from the libusb-package project:
https://github.com/pyusb/libusb-package
"""


def copy_python_license(target):
    """Python's own license file lives in the folder of the Python that
    made the build environment (sys.base_prefix)."""
    for name in ("LICENSE.txt", "LICENSE"):
        for folder in (Path(sys.base_prefix), Path(sys.base_prefix) / "lib"):
            candidates = [folder / name] + list(folder.glob(f"python3*/{name}"))
            for candidate in candidates:
                if candidate.exists():
                    (target / "python").mkdir(exist_ok=True)
                    shutil.copy(candidate, target / "python" / "LICENSE.txt")
                    return
    print(f"Warning: Python's license file not found near {sys.base_prefix}")


def copy_package_licenses(target, name):
    distribution = metadata.distribution(name)
    folder = target / name
    folder.mkdir(exist_ok=True)
    copied = 0
    for file in distribution.files or []:
        if file.name.upper().startswith(LICENSE_WORDS):
            shutil.copy(file.locate(), folder / file.name)
            copied += 1
    if copied == 0:
        # Some packages (python-osc) only name their license in their
        # description. Keep that, so the license is still on record.
        license_name = (distribution.metadata.get("License-Expression")
                        or distribution.metadata.get("License") or "see the project's website")
        (folder / "LICENSE.txt").write_text(
            f"{name} {distribution.version}\nLicense: {license_name}\n"
            f"Project: {distribution.metadata.get('Home-page') or ''}\n", encoding="utf-8")
    print(f"  {name}: {copied or 'description only'}")


def main():
    target = Path(sys.argv[1])
    packages = sys.argv[2:] or DEFAULT_PACKAGES
    target.mkdir(parents=True, exist_ok=True)

    copy_python_license(target)
    for name in packages:
        copy_package_licenses(target, name)
    if "libusb1" in packages:
        (target / "libusb").mkdir(exist_ok=True)
        (target / "libusb" / "LICENSE-NOTE.txt").write_text(LIBUSB_NOTE, encoding="utf-8")


if __name__ == "__main__":
    main()
