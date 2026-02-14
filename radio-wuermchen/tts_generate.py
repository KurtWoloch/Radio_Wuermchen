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
from pathlib import Path
import subprocess
import wave
from google import genai
from google.genai import types

# --- CONFIGURATION ---
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = SCRIPT_DIR / "tts_config.json"
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"

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

# --- MAIN ---
def generate(text_file):
    if not os.path.exists(text_file):
        print(f"ERROR: Text file not found: {text_file}", file=sys.stderr)
        return False

    # Derive output path: temporary WAV name, final MP3 name
    base, _ = os.path.splitext(text_file)
    wav_path = base + ".wav"
    mp3_path = base + ".mp3"

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
    
    try:
        # 1. Call Google TTS API
        client = genai.Client(api_key=config["api_key"])
        
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
            return False
            
        part = response.candidates[0].content.parts[0]
        if not hasattr(part, 'inline_data') or not hasattr(part.inline_data, 'data'):
            print(f"TTS API returned part without expected inline_data structure: {part}", file=sys.stderr)
            return False

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
        
        # 2. Save WAV or MP3
        if mime_type and 'audio/mp3' in mime_type.lower():
            print("DEBUG: Detected MP3 audio stream. Writing directly to MP3.")
            with open(mp3_path, 'wb') as f:
                f.write(audio_data)
        else:
            # Default/Fallback: Save as WAV, then convert to MP3
            print(f"DEBUG: Saving via WAV intermediate step.")
            if not wave_file(wav_path, audio_data):
                return False

            # 3. Convert WAV to MP3 using FFmpeg
            ffmpeg_cmd = [
                FFMPEG_BIN,
                "-y",           # overwrite output without asking
                "-i", wav_path, # Explicitly state input format is WAV
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                mp3_path
            ]

            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            
    except Exception as e:
        print(f"TTS Generation/Conversion Error: {e}", file=sys.stderr)
        # WAV file will be left behind due to KEEP_WAV=True below
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