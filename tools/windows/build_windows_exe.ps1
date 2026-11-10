# SPDX-License-Identifier: AGPL-3.0-or-later
# build_windows_exe.ps1
#
# Builds "RealSense Depth Server.exe": a double-click program for Windows
# users that contains the depth server and everything it needs (Python,
# numpy, OpenCV, ...). People who download it install nothing else.
#
# For developers only. You do not need this script to use the program.
#
# Usage (in PowerShell, from the main project folder, on a Windows PC):
#   powershell -ExecutionPolicy Bypass -File tools\windows\build_windows_exe.ps1
#
# ("-ExecutionPolicy Bypass" lets Windows run this one script without
# changing any setting on your computer.)
#
# Result:
#   dist\RealSense Depth Server\                   the program folder
#   dist\RealSense-Depth-Server-Windows.zip        the file to share
#
# What you need once:
#   - 64-bit Python 3.11 or newer from https://www.python.org/downloads/windows/
#     (the installer also installs the "py" command this script uses). To
#     use a specific Python, add:  -Python "C:\path\to\python.exe"
#   - An internet connection (the script downloads packages with pip).
#
# Everything the script downloads or builds goes into the folder .build\,
# which git ignores. Delete it to start from scratch.

param(
    [string] $Python = ""
)

# Stop at the first error, like "set -e" in a shell script.
$ErrorActionPreference = "Stop"

$Project = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Build = Join-Path $Project ".build\windows"
$Dist = Join-Path $Project "dist"
$AppName = "RealSense Depth Server"
$Zip = Join-Path $Dist "RealSense-Depth-Server-Windows.zip"

# Runs a program and stops the script if it reports an error. (PowerShell
# does not stop by itself when a normal program, like pip, fails.)
function Run {
    param([string] $Program, [string[]] $Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "This step failed: $Program $($Arguments -join ' ')"
    }
}

# --- 1. Check the Python -----------------------------------------------------
if (-not $Python) {
    # "py -3" is the Python launcher from python.org; it finds the newest
    # Python 3. We ask it where that Python lives.
    $Python = (& py -3 -c "import sys; print(sys.executable)").Trim()
}
$check = & $Python -c "import sys, struct; print(sys.version_info >= (3, 11), struct.calcsize('P') * 8)"
if ($check -ne "True 64") {
    Write-Host "Please use a 64-bit Python 3.11 or newer (found: $Python, $check)."
    exit 1
}
Write-Host "1/5 Using $Python"

# --- 2. A separate build environment --------------------------------------
# We do not touch .venv (used to run the server from a terminal).
$Venv = Join-Path $Build "venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
# (If you switch to another Python, delete .build\windows first, so the
# build environment is made again with the new one.)
if (-not (Test-Path $VenvPython)) {
    Run $Python @("-m", "venv", $Venv)
}
# The version numbers are fixed (pinned), also for the helpers PyInstaller
# uses, so the build gives (almost) the same result every time. These are
# the versions the program was tested with, built with Python 3.13. When you
# update them, test the program again with a real camera.
Run $VenvPython @("-m", "pip", "install", "-q", "pip==26.3")
# opencv-python-headless is the smaller OpenCV without windows, which is
# all the server needs.
Run $VenvPython @("-m", "pip", "install", "-q",
    "pyinstaller==6.22.3", "pyinstaller-hooks-contrib==2026.10",
    "altgraph==0.17.5", "pefile==2024.8.26", "numpy==2.5.4", "opencv-python-headless==5.0.0.93",
    "websockets==17.4", "python-osc==1.10.2")
Write-Host "2/5 Build environment ready"

# --- 3. Freeze the server with PyInstaller -----------------------------------
# PyInstaller collects Python and every package the server uses into one
# folder, with "RealSense Depth Server.exe" inside.
#   --console:  the program shows a console window with the server's
#               messages, so people see what to write in their sketch
#   --exclude-module capture_linux / capture_macos / usb1:
#               the camera code for the other systems, not needed here
$Work = Join-Path $Build "pyinstaller"
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
Run $VenvPython @("-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
    "--onedir", "--console", "--name", $AppName,
    "--distpath", (Join-Path $Work "dist"), "--workpath", (Join-Path $Work "work"),
    "--specpath", $Work,
    "--paths", (Join-Path $Project "server"),
    "--add-data", "$(Join-Path $Project 'server\config.toml');.",
    "--exclude-module", "capture_linux", "--exclude-module", "capture_macos",
    "--exclude-module", "usb1",
    (Join-Path $Project "server\depth_server.py"))
Write-Host "3/5 Server frozen"

# --- 4. Put the program folder together -----------------------------------
$AppFolder = Join-Path $Dist $AppName
if (Test-Path $AppFolder) { Remove-Item -Recurse -Force $AppFolder }
New-Item -ItemType Directory -Force $Dist | Out-Null
Copy-Item -Recurse (Join-Path $Work "dist\$AppName") $AppFolder
Copy-Item (Join-Path $Project "tools\windows\windows_exe\READ ME FIRST.txt") $AppFolder
# The licenses travel with the program, as open source licenses ask:
# our own (LICENSE.txt) and those of every part inside it (licenses\).
Copy-Item (Join-Path $Project "LICENSE") (Join-Path $AppFolder "LICENSE.txt")
Run $VenvPython @((Join-Path $Project "tools\collect_licenses.py"), (Join-Path $AppFolder "licenses"))
Write-Host "4/5 Program folder ready"

# --- 5. Zip it ---------------------------------------------------------------------
if (Test-Path $Zip) { Remove-Item -Force $Zip }
# We use Python's zip tool instead of PowerShell's Compress-Archive (or
# .NET): those write folder names with "\" inside the zip on some Windows
# versions, which unzip programs on other systems do not understand.
# Python always writes "/", the standard.
Run $VenvPython @("-m", "zipfile", "-c", $Zip, $AppFolder)
$size = [math]::Round((Get-Item $Zip).Length / 1MB)
Write-Host "5/5 Done:"
Write-Host "    $AppFolder\$AppName.exe"
Write-Host "    $Zip ($size MB)"
