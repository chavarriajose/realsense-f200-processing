# SPDX-License-Identifier: AGPL-3.0-or-later
# run_sketch_windows.ps1
#
# Runs one Processing example on this Windows PC and saves a screenshot. The
# project uses it to test the examples automatically. You do not need it to
# use the examples: simply press Run in Processing.
#
# Usage (in PowerShell, from the main project folder, with the server running):
#   powershell -ExecutionPolicy Bypass -File tools\windows\run_sketch_windows.ps1 processing\example01_show_depth example01.png
#
# ("-ExecutionPolicy Bypass" lets Windows run this one script without
# changing any setting on your computer.)
#
# The sketch window opens for a few seconds and closes by itself.
# By default the sketch finds the server by itself (SERVER = "auto").
# To use a fixed address instead, add:   -Server 127.0.0.1
#
# It needs Processing 4. The script looks for processing-java.exe (the
# command line version of Processing, which comes with it) in the usual
# places. If yours is somewhere else, add:
#   -Processing "C:\path\to\processing-4.3\processing-java.exe"
# Example 05 also needs the oscP5 library (Processing's Contribution Manager).

param(
    [Parameter(Mandatory = $true)] [string] $Sketch,
    [Parameter(Mandatory = $true)] [string] $Screenshot,
    [string] $Server = "",
    [string] $Processing = $env:PROCESSING
)

# --- Find processing-java.exe ----------------------------------------------
if (-not $Processing) {
    # The installer puts Processing in "Program Files" or in your own
    # programs folder. Many people simply unzip it, often into Documents
    # or Downloads, so we look there too (newest version first).
    $candidates = @(
        "$env:ProgramFiles\Processing\processing-java.exe",
        "$env:LOCALAPPDATA\Programs\Processing\processing-java.exe"
    )
    foreach ($folder in @("$HOME\Documents", "$HOME\Downloads", "$HOME\Desktop", "C:\")) {
        $found = Get-ChildItem -Path $folder -Filter "processing-4*" -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "processing-java.exe" }
        $candidates += $found
    }
    $Processing = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Processing -or -not (Test-Path $Processing)) {
    Write-Host "Could not find processing-java.exe. Add -Processing <path to processing-java.exe>."
    exit 1
}

# --- Check the folders -------------------------------------------------------
if (-not (Test-Path -PathType Container $Sketch)) {
    Write-Host "Sketch folder not found: $Sketch"
    exit 1
}
$sketchFolder = (Resolve-Path $Sketch).Path

# A screenshot name without a folder (like example01.png) goes into the
# current folder.
$screenshotFolder = Split-Path -Parent $Screenshot
if (-not $screenshotFolder) { $screenshotFolder = "." }
if (-not (Test-Path -PathType Container $screenshotFolder)) {
    Write-Host "Folder for the screenshot not found: $screenshotFolder"
    exit 1
}
$screenshotPath = Join-Path (Resolve-Path $screenshotFolder).Path (Split-Path -Leaf $Screenshot)

# --- Run the sketch ----------------------------------------------------------

# Remove an old screenshot first, so we never report an old picture as new.
if (Test-Path $screenshotPath) { Remove-Item $screenshotPath }

$arguments = @("--sketch=`"$sketchFolder`"", "--run")
# Only pass --server when an address was given, so "auto" is tested otherwise.
if ($Server) { $arguments += "--server=$Server" }
$arguments += "--screenshot=`"$screenshotPath`""

# Processing prints its messages into these two files; we show them after.
$outputFile = [System.IO.Path]::GetTempFileName()
$errorFile = [System.IO.Path]::GetTempFileName()
$run = Start-Process -FilePath $Processing -ArgumentList $arguments -NoNewWindow -PassThru `
    -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile

# Stop the sketch after 90 seconds if something hangs.
if (-not $run.WaitForExit(90000)) {
    Write-Host "The sketch did not finish within 90 seconds, stopping it."
    # /T also stops the Java program that runs the sketch, not only
    # processing-java.exe, which started it.
    taskkill /T /F /PID $run.Id | Out-Null
}
Get-Content $outputFile, $errorFile
Remove-Item $outputFile, $errorFile -ErrorAction SilentlyContinue

if (Test-Path $screenshotPath) {
    Write-Host "OK: $screenshotPath"
} else {
    Write-Host "FAILED: no screenshot saved. Is the server running? See the messages above."
    exit 1
}
