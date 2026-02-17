# TTS Generator (Black Box) - Google Gemini Edition
#
# Usage: python tts_generate.py <text_file>
#
# Takes a path to a text file, reads its content, converts it to speech
# using the configured Google TTS model, and outputs an MP3 file with the same
# base name but the .mp3 extension.
#
# Dependencies: google-genai, ffmpeg

import json
import sys
import os
import base64
import time
from pathlib import Path
import subprocess
import wave
from google import genai
from google.genai import types

# --- CONFIGURATION ---
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = SCRIPT_DIR / "tts_config.json"
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
RATE_LIMIT_WARN_FILE = SCRIPT_DIR / "tts_rate_limit.warn"
RATE_LIMIT_COOLDOWN = 3600  # 1 hour in seconds

# --- HELPERS ---
def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error reading JSON file {path}: {e}", file=sys.stderr)
        return {}

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Saves raw PCM data to a WAV file (matching example function name)."""
    try:
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)
        return True
    except Exception as e:
        print(f"Error saving WAV file {filename}: {e}", file=sys.stderr)
        return False

def is_rate_limited():
    """Check if we're in a rate limit cooldown period. Deletes stale warn files."""
    if RATE_LIMIT_WARN_FILE.exists():
        age = time.time() - os.path.getmtime(RATE_LIMIT_WARN_FILE)
        if age < RATE_LIMIT_COOLDOWN:
            remaining = int(RATE_LIMIT_COOLDOWN - age)
            print(f"WARNING: Rate limit cooldown active ({remaining}s remaining). Using local TTS.", file=sys.stderr)
            return True
        else:
            print("INFO: Rate limit cooldown expired. Removing warn file, retrying Google API.", file=sys.stderr)
            RATE_LIMIT_WARN_FILE.unlink()
    return False

def set_rate_limited(error_message=""):
    """Create the rate limit warning file with the error details."""
    content = f"Rate limited at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    if error_message:
        content += f"Error: {error_message}\n"
    RATE_LIMIT_WARN_FILE.write_text(content, encoding="utf-8")
    print(f"WARNING: Created rate limit warn file. Will use local TTS for {RATE_LIMIT_COOLDOWN}s.", file=sys.stderr)

def detect_language(text):
    """Detect if text is likely German based on umlaut frequency.
    Returns 'de' if multiple umlauts found, 'en' otherwise."""
    umlauts = sum(1 for c in text if c in 'äöüÄÖÜß')
    if umlauts >= 2:
        return 'de'
    return 'en'

def generate_local_tts(text_file, wav_path):
    """Fall back to Windows SAPI local TTS generation.
    Automatically detects German text and switches voice accordingly."""
    # Read text to detect language
    with open(str(text_file), 'r', encoding='utf-8') as f:
        text_content = f.read()

    lang = detect_language(text_content)
    if lang == 'de':
        voice_name = 'Microsoft Hedda Desktop - German'
        voice_lang = '407'
        print("INFO: Falling back to local SAPI TTS (Microsoft Hedda - German)...", file=sys.stderr)
    else:
        voice_name = 'Microsoft Zira Desktop - English (United States)'
        voice_lang = '409'
        print("INFO: Falling back to local SAPI TTS (Microsoft Zira - English)...", file=sys.stderr)

    text_file_escaped = str(text_file).replace("'", "''")
    wav_path_escaped = str(wav_path).replace("'", "''")
    powershell_cmd = (
        f"$speak = New-Object -ComObject 'SAPI.SpVoice'; "
        f"$stream = New-Object -ComObject 'SAPI.SpFileStream'; "
        f"$stream.Open('{wav_path_escaped}', 3, $false); "
        f"$speak.AudioOutputStream = $stream; "
        f"$voice = $speak.GetVoices() | Where-Object {{ $_.GetAttribute('Language') -eq '{voice_lang}' "
        f"-and $_.GetDescription() -eq '{voice_name}' }}; "
        f"$speak.Voice = $voice; "
        f"$speak.Speak([System.IO.File]::ReadAllText('{text_file_escaped}')); "
        f"$stream.Close(); $speak = $null;"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell_cmd],
            check=True, capture_output=True, text=True
        )
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            print(f"INFO: Local TTS generated WAV: {wav_path}", file=sys.stderr)
            return True
        else:
            print("ERROR: Local TTS produced no output.", file=sys.stderr)
            return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Local TTS failed: {e.stderr}", file=sys.stderr)
        return False

# --- MAIN ---
def generate(text_file):
    if not os.path.exists(text_file):
        print(f"ERROR: Text file not found: {text_file}", file=sys.stderr)
        return False

    # Derive output path: temporary WAV name, final MP3 name
    base, _ = os.path.splitext(text_file)
    wav_path = base + ".wav"
    mp3_path = base + ".mp3"

    # Clean up stale output files from previous runs
    if os.path.exists(mp3_path):
        os.remove(mp3_path)
    if os.path.exists(wav_path):
        os.remove(wav_path)

    # Read the text
    with open(text_file, 'r', encoding='utf-8') as f:
        text_content = f.read().strip()

    if not text_content:
        print(f"ERROR: Text file is empty: {text_file}", file=sys.stderr)
        return False

    # Load TTS Configuration
    config = load_json(CONFIG_FILE)
    if not config or config.get("api_key", "").startswith("YOUR_"):
        print("ERROR: Cannot load tts_config.json or API key is missing.", file=sys.stderr)
        return False

    use_local_tts = False

    # Check rate limit cooldown before attempting Google API
    if is_rate_limited():
        use_local_tts = True

    if not use_local_tts:
        try:
            # 1. Call Google TTS API
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
                return False

            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=config["tts_model"],
                contents=[{"text": text_content}],
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=config["voice_name"]
                            )
                        )
                    )
                )
            )

            # DEBUG: Inspect response structure
            if not response.candidates or not response.candidates[0].content.parts:
                print(f"TTS API returned no candidates/parts: {response.prompt_feedback}", file=sys.stderr)
                raise RuntimeError("Google TTS returned no audio data")
                
            part = response.candidates[0].content.parts[0]
            if not hasattr(part, 'inline_data') or not hasattr(part.inline_data, 'data'):
                print(f"TTS API returned part without expected inline_data structure: {part}", file=sys.stderr)
                raise RuntimeError("Google TTS returned unexpected data structure")

            data_payload = part.inline_data.data
            mime_type = part.inline_data.mime_type
            print(f"DEBUG: Received data payload of length: {len(data_payload)} characters.", file=sys.stderr)
            print(f"DEBUG: Detected MIME Type: {mime_type}", file=sys.stderr)
            
            audio_data = None
            
            # LOGIC CHANGE: Check MIME type strictly for PCM (lowercase 'l16')
            if mime_type and 'audio/l16' in mime_type.lower():
                print("DEBUG: Detected raw PCM audio stream. Using data directly.", file=sys.stderr)
                audio_data = data_payload # Use raw data as PCM
            else:
                # Fallback: Assume Base64 encoded (MP3 or otherwise)
                print("DEBUG: Assuming Base64 encoded audio format. Decoding...", file=sys.stderr)
                audio_data = base64.b64decode(data_payload, validate=False)
            
            # DEBUG: Print size of processed data
            print(f"DEBUG: Processed data size: {len(audio_data)} bytes.", file=sys.stderr)
            
            if len(audio_data) < 500: # Heuristic check for tiny files
                 print(f"WARNING: Processed data size ({len(audio_data)} bytes) is too small for audio.", file=sys.stderr)
            
            # 2. Save WAV or direct MP3
            if mime_type and 'audio/mp3' in mime_type.lower():
                print("DEBUG: Detected MP3 audio stream. Writing directly to MP3.")
                with open(mp3_path, 'wb') as f:
                    f.write(audio_data)
            else:
                # Save as WAV (will be converted to MP3 below)
                print(f"DEBUG: Saving via WAV intermediate step.")
                if not wave_file(wav_path, audio_data):
                    raise RuntimeError("Failed to write WAV file from Google TTS data")

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "quota" in error_str or "429" in error_str or "resource" in error_str:
                print(f"WARNING: Google TTS rate limited: {e}", file=sys.stderr)
                set_rate_limited(str(e))
            else:
                print(f"WARNING: Google TTS failed: {e}", file=sys.stderr)
                set_rate_limited(str(e))
            use_local_tts = True

    # --- LOCAL TTS FALLBACK ---
    if use_local_tts:
        if not generate_local_tts(text_file, wav_path):
            print("ERROR: Both Google and local TTS failed.", file=sys.stderr)
            return False

    # --- CONVERT WAV TO MP3 (if MP3 wasn't written directly) ---
    try:
        if os.path.exists(mp3_path):
            print(f"DEBUG: MP3 already exists, skipping conversion: {mp3_path}", file=sys.stderr)
        elif not os.path.exists(wav_path):
            print("ERROR: No WAV or MP3 file produced.", file=sys.stderr)
            return False
        else:
            print(f"DEBUG: Converting WAV to MP3: {wav_path} -> {mp3_path}", file=sys.stderr)
            ffmpeg_cmd = [
                FFMPEG_BIN,
                "-y",           # overwrite output without asking
                "-i", str(wav_path),
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                str(mp3_path)
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True)
            if result.returncode != 0:
                print(f"FFmpeg stderr: {result.stderr.decode(errors='replace')}", file=sys.stderr)
                return False
            if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
                print("ERROR: FFmpeg ran but MP3 file is missing or empty.", file=sys.stderr)
                return False
            print(f"DEBUG: MP3 conversion successful ({os.path.getsize(mp3_path)} bytes)", file=sys.stderr)
    except Exception as e:
        print(f"FFmpeg Conversion Error: {e}", file=sys.stderr)
        return False
    finally:
        # Cleanup temporary WAV file
        KEEP_WAV = True # Set to True to keep the file for inspection
        if not KEEP_WAV and os.path.exists(wav_path):
            os.remove(wav_path)
        elif KEEP_WAV:
            print(f"DEBUG: Kept WAV file for inspection: {wav_path}", file=sys.stderr)


    print(f"OK: {mp3_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <text_file>", file=sys.stderr)
        sys.exit(1)

    success = generate(sys.argv[1])
    sys.exit(0 if success else 1)