# Liquidsoap Script for Radio Wuermchen - stream.liq (Final Working Output)

# --- CONFIGURATION ---
set("log.level", 3)
set("title", "Radio Wuermchen")
set("public", true)

# --- CORE SOURCE DEFINITION ---
# Input using the local test file. The FFmpeg input should decode this.
s = single("C:/Users/kurt_/.openclaw/workspace/2 Unlimited - No limit.mp3")

# --- OUTPUT (The Broadcast Tower) ---

# Output to Icecast in a minimal, supported configuration.
output.icecast(
  %ffmpeg(mime="audio/mpeg", codec="libmp3lame"), # Use generic FFmpeg
  fallible=true, # Use the supported fallible option
  host="localhost",
  port=8000,
  password="hackme",
  mount="/radio.mp3",
  s
)
