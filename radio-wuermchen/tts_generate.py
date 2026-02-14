# TTS Generator (Black Box)
#
# Usage: python tts_generate.py <text_file>
#
# Takes a fully qualified path to a text file, reads its content,
# converts it to speech, and outputs an MP3 file with the same name
# but .mp3 extension in the same directory.
#
# Example:
#   python tts_generate.py C:\path\to\announcement.txt
#   -> produces C:\path\to\announcement.mp3
#
# Current method: Windows SAPI (Microsoft Zira) via PowerShell, then
# FFmpeg to convert WAV to MP3.
#
# To swap TTS engines later, only this file needs to change.

import subprocess
import sys
import os
import tempfile

# --- CONFIGURATION ---
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"

# --- MAIN ---
def generate(text_file):
    if not os.path.exists(text_file):
        print(f"ERROR: Text file not found: {text_file}", file=sys.stderr)
        return False

    # Derive output path: same name, .mp3 extension
    base, _ = os.path.splitext(text_file)
    mp3_path = base + ".mp3"
    wav_path = base + ".wav"  # temporary intermediate file

    # Read the text
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read().strip()

    if not text:
        print(f"ERROR: Text file is empty: {text_file}", file=sys.stderr)
        return False

    # --- Step 1: Text to WAV via Windows SAPI (PowerShell) ---
    # Escape single quotes in the file path for PowerShell
    safe_text_file = text_file.replace("'", "''")
    safe_wav_path = wav_path.replace("'", "''")

    powershell_cmd = (
        "$speak = New-Object -ComObject 'SAPI.SpVoice'; "
        "$stream = New-Object -ComObject 'SAPI.SpFileStream'; "
        f"$stream.Open('{safe_wav_path}', 3, $false); "
        "$speak.AudioOutputStream = $stream; "
        "$voice = $speak.GetVoices() | Where-Object { "
        "  $_.GetAttribute('Language') -eq '409' -and "
        "  $_.GetDescription() -eq 'Microsoft Zira Desktop - English (United States)' "
        "}; "
        "$speak.Voice = $voice; "
        f"$speak.Speak([System.IO.File]::ReadAllText('{safe_text_file}')); "
        "$stream.Close(); $speak = $null;"
    )

    try:
        result = subprocess.run(
            ["powershell", "-Command", powershell_cmd],
            check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"SAPI Error: {e.stderr}", file=sys.stderr)
        return False

    if not os.path.exists(wav_path):
        print(f"ERROR: SAPI did not produce WAV file: {wav_path}", file=sys.stderr)
        return False

    # --- Step 2: WAV to MP3 via FFmpeg ---
    ffmpeg_cmd = [
        FFMPEG_BIN,
        "-y",           # overwrite output without asking
        "-i", wav_path,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        mp3_path
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e.stderr.decode('utf-8')}", file=sys.stderr)
        return False

    # Clean up temporary WAV
    try:
        os.remove(wav_path)
    except Exception:
        pass

    print(f"OK: {mp3_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <text_file>", file=sys.stderr)
        sys.exit(1)

    success = generate(sys.argv[1])
    sys.exit(0 if success else 1)
