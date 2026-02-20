# Radio Würmchen - Technical Architecture

## Project Overview

Radio Würmchen is a fully autonomous, AI-curated internet radio station built by Kurt Woloch in Vienna, Austria. It streams a continuous mix of music from a personal library of 20,000+ MP3 files, interspersed with AI-generated DJ announcements, news segments, weather updates, and chart integrations.

The station operates under the persona "DJ Würmchen" and runs entirely on a Windows 10 PC using Python scripts, FFmpeg, Icecast, and Google Gemini APIs. It is designed for low-latency streaming with external access currently provided via an ngrok tunnel (with Cloudflare Tunnel under consideration).

## Architecture Layers

The system is composed of several distinct layers that handle specific responsibilities, from audio streaming to content generation and listener interaction.

### 1. Streaming Layer (The Audio Pipeline)

This layer is responsible for the continuous audio output to the broadcast server.

*   **Icecast** (`icecast.xml`, port 8000)
    *   The core broadcast server.
    *   Mountpoint: `/stream`.

*   **streamer.py**
    *   The queue-based streaming engine.
    *   **Functionality:**
        *   Reads file paths from `queue.txt` (one per line).
        *   Streams each file via FFmpeg to stdout in real-time (using the `-re` flag) as MP3.
        *   Monitors queue depth; writes `queue_low.signal` when ≤2 items remain to trigger the orchestrator.
        *   Handles empty queues by repeating the last played track to prevent dead air.
        *   Skips immediate repeats of the same track.
        *   Output is piped to an outer FFmpeg process that pushes the stream to Icecast.
    *   **Logging:** Writes to `streamer.log`.

*   **Batch Launchers**
    *   `run_streamer.bat`: Sets up the full pipe chain: `python radio_streamer.py | ffmpeg -> icecast`.
    *   `run_dj_streamer.bat`: Runs the streamer directly, assuming Icecast is already running.

*   **queue_filler.py**
    *   A fallback mechanism.
    *   Watches for `queue_low.signal` and appends tracks from a sequential playlist walk (random start).
    *   Used as a basic non-AI backup when the main orchestrator is inactive.

*   **Legacy Components**
    *   `radio_streamer.py`: An older pipe-writer streamer that used file polling for DJ communication. Superseded by the current queue-based architecture but retained in the codebase.

### 2. Intelligence Layer (DJ Brain & Orchestrator)

The intelligence layer manages the station's content flow, decision-making, and "personality."

*   **dj_orchestrator.py**
    *   The central control hub (~1000 lines of code).
    *   **Core Loop:** Polls for `queue_low.signal` every 3 seconds.
    *   **Execution Cycle:**
        1.  **Show Detection:** Checks `shows_schedule.json` for the active show and handles transitions (including signation tracks).
        2.  **Power Saving:** If no Icecast listeners or requests are active, skips LLM/TTS generation and queues directly from suggestion pools.
        3.  **Context Gathering:** Aggregates data from `weather_manager`, `news_scheduler`, and `charts_in_library.json`.
        4.  **DJ Brain Execution:** Calls `dj_brain.py` with context to get a track suggestion and announcement.
        5.  **Track Matching:** Resolves the suggestion to a file using a 3-tier priority:
            *   *Priority 1:* Exact raw match.
            *   *Priority 2:* Alias-based match (via `track_aliases.json`).
            *   *Priority 3:* Cleaned/fuzzy match (strips metadata tags, matches by length similarity).
        6.  **History Check:** Enforces a 50-track non-repeat buffer (`dj_history.json`).
        7.  **Fallback Cascade:** If a track is not found, retries up to 5 times using:
            *   News-relevant extraction.
            *   Show-specific suggestion pools.
            *   Artist alternatives.
            *   Different artist requests to the DJ.
        8.  **TTS Generation:** Sends text to `tts_manager` for audio creation.
        9.  **Queue Management:** Appends the announcement MP3 and track MP3 to `queue.txt`.
        10. **Wishlist:** Logs unavailable suggestions to `Wishlist.txt`.
        11. **Pool Rotation:** In power-save mode, recycles used suggestions to the bottom of the pool.
        12. **Charts Check:** Triggers `charts_scraper.py` once daily.

*   **dj_brain.py**
    *   The LLM interface script.
    *   Reads `dj_request.json` (context, instructions).
    *   Constructs a system prompt defining DJ Würmchen (natural, energetic, concise).
    *   Enforces genre diversity (bans repeating the same genre twice).
    *   Calls **Google Gemini** (model: `gemini-2.5-flash`) via `google-genai` SDK.
    *   Outputs JSON with "track" and "announcement" fields to `dj_response.json`.
    *   Configured via `dj_config.json`.

*   **track_aliases.json**
    *   A manual lookup table for normalizing track names.
    *   Maps colloquial titles (e.g., "Falco - Amadeus") to filesystem names ("Falco - Rock Me Amadeus").

### 3. Content Layer (News, Weather, Charts)

This layer gathers real-world data to make the broadcast live and relevant.

*   **news_manager.py**
    *   Scrapes **orf.at** (Austrian national broadcaster).
    *   Parses breaking news, top stories, regular stories, and quicklinks.
    *   Fetches sub-story descriptions for top stories (JSON-LD extraction).
    *   Caches content in `news_cache.json` (60-minute TTL) and tracks presented stories to prevent repetition.

*   **news_scheduler.py**
    *   Determines news presentation logic per DJ cycle.
    *   **Headlines:** Presented every 60 minutes.
    *   **Deep Dives:** Individual unpresented stories presented between headline blocks.
    *   Can be disabled per-show via configuration.

*   **weather_manager.py**
    *   Fetches weather using `scraper.py` and `templates/weather_vienna.txt`.
    *   Caches results for 30 minutes.
    *   **Logic:** Fresh scrape triggers a full forecast; cached data triggers a subtle weather mention.

*   **charts_scraper.py**
    *   Scrapes **austriancharts.at** (Austrian Singles Top 75).
    *   Runs daily via orchestrator trigger.
    *   Matches chart entries against the local library (`charts_in_library.json`).
    *   Rebuilds `suggestion_pool_modern.txt` with chart hits prioritized.
    *   Triggers `generate_pools.py`.

*   **scraper.py**
    *   A generic, template-driven web scraper used by the weather manager.
    *   Uses start/end anchors to extract fields sequentially.

### 4. TTS Layer (Text-to-Speech)

*   **tts_generate.py**
    *   **Primary Engine:** Google Gemini TTS API (`gemini-2.5-flash-preview-tts`, voice: "Kore").
    *   **Fallback Engine:** Windows SAPI (Microsoft Hedda/Zira).
    *   **Features:**
        *   Auto-detects language (German if umlauts ≥ 2, else English).
        *   Handles rate limits with a 1-hour cooldown file (`tts_rate_limit.warn`).
        *   Converts responses to MP3 (192kbps) via FFmpeg.

*   **tts_manager.py**
    *   Manages a rotating set of 10 announcement slots (`temp_announcement1-10.mp3`).
    *   Enforces a 30-minute minimum age before reusing slots to ensure playback stability.
    *   Implements a 120-second timeout for generation.

### 5. Show Schedule System

Defined in `shows_schedule.json`. The schedule dictates the music style, DJ personality, and content rules for specific time blocks.

**Current Schedule:**

| Time | Show Name | Style / Theme |
| :--- | :--- | :--- |
| **09:00 - 10:00** | Please be friendly | Positive, happy tracks |
| **10:00 - 11:00** | Classic Crooners | Sinatra, Dean Martin era |
| **11:00 - 12:00** | Music for Young People (AM) | 2010s-2020s hits |
| **13:00 - 15:00** | Espresso | Bossa nova, nu-jazz, acoustic |
| **15:00 - 16:00** | The Music Box | Indie, alternative, experimental |
| **16:00 - 17:00** | Evergreens | Pre-1970s strictly |
| **17:00 - 18:00** | Super Hits | 70s and 80s |
| **19:00 - 22:00** | Music for Young People (PM) | 2010s-2020s hits |
| **23:00 - 00:00** | Music for Dreaming | Soft, relaxing, easy listening |
| **00:00 - 06:00** | Night Rock Show | Rock for US listeners |
| *(Gaps)* | Freeform | General suggestion pool |

*   **Transitions:** The system looks ahead 4 minutes. If a transition is imminent, it plays a signation track (if configured) and the DJ announces the new show.

### 6. Suggestion Pool System

*   **generate_pools.py**
    *   Generates show-specific text files from the master playlist based on artist names and keywords.
    *   Pools include: `ratpack`, `espresso`, `indie`, `evergreens`, `superhits`, `friendly`, `modern`, `dreaming`, `night_rock`, and `general`.
    *   Some pools utilize exclusion keywords (e.g., "friendly" excludes violent terms).
    *   Orchestrator consumes these pools; in power-save mode, tracks are rotated back to the bottom.

### 7. Web / Listener Layer

*   **listener_server.py** (Port 8001)
    *   Serves the station website (Dark theme, green accents).
    *   **Features:**
        *   Embedded HTML5 audio player.
        *   Live metadata: Show name, listener count, recently played (last 5).
        *   **Request System:** Listener request form (Rate limited: 1 per IP/2 mins).
        *   **Proxy:** Proxies the Icecast stream at `/stream` to allow single-port external access.
        *   **Now Playing:** Updates via `/nowplaying` JSON endpoint every 60s.
        *   **Traffic Management:** Tracks proxy connections to deduct from Icecast stats (preventing double-counting).

*   **Launchers**
    *   `start_external_stream.bat`: Starts server + ngrok tunnel.
    *   `start_listener_server.bat`: Starts server only (local).

### 8. Music Library

*   **Location:** `E:\Daten\Radio Würmchen\Musik`
*   **Size:** 20,000+ MP3 files.
*   **Convention:** `Artist - Title.mp3` (supports `feat.` tags and parentheses).
*   **generate_playlist.py:** Scans the directory recursively to generate `music.playlist` (absolute paths).

### 9. Data Files Summary

| File | Purpose |
| :--- | :--- |
| `queue.txt` | Active playback queue (consumed by streamer). |
| `queue_low.signal` | Signal file triggers orchestrator when queue ≤ 2. |
| `dj_request.json` | Context payload sent to DJ Brain. |
| `dj_response.json` | JSON response from DJ Brain (track + text). |
| `dj_history.json` | Last 50 tracks (repeat prevention). |
| `shows_schedule.json` | Daily program schedule and overrides. |
| `track_aliases.json` | Manual alias mapping for track names. |
| `charts_in_library.json` | Chart songs identified in the library. |
| `news_cache.json` | Cached stories from orf.at. |
| `Wishlist.txt` | Tracks suggested by DJ but missing from library. |
| `listener_request.txt` | Pending listener request. |
| `orchestrator.log` | Main system log. |
| `streamer.log` | Audio pipeline log. |

### 10. External Dependencies

*   **Python 3.11**
*   **FFmpeg** (via MSYS2/MinGW)
*   **Icecast** (Local streaming server)
*   **Google Gemini API** (LLM & TTS via `google-genai` SDK)
*   **Mutagen** (Python MP3 tag library)
*   **Ngrok** (External tunneling)

### 11. Process Architecture (Runtime)

The system relies on five active processes:

1.  **Icecast** (Port 8000)
2.  **streamer.py** (Audio pipeline)
3.  **dj_orchestrator.py** (Logic/Intelligence)
4.  **listener_server.py** (Web/Proxy, Port 8001)
5.  **ngrok** (Tunnel)

**Data Flow:**

```text
streamer.py reads queue.txt → streams via FFmpeg → Icecast (:8000)
                                                      ↑
queue_low.signal ← streamer (when queue ≤ 2)          |
      ↓                                               |
dj_orchestrator.py                                    |
  ├─ dj_brain.py (Gemini API) → track + announcement  |
  ├─ tts_generate.py (Gemini TTS) → announcement.mp3  |
  ├─ weather_manager.py → weather context             |
  ├─ news_scheduler.py → news context                 |
  └─ appends to queue.txt ────────────────────────────┘

listener_server.py (:8001) → proxies /stream from Icecast
ngrok → tunnels :8001 to public URL
```

### 12. Historical & Design Notes

*   **Superseded Docs:** `PROJECT_SPEC.md` and `RADIO_VISION.md` are outdated; this document is the source of truth.
*   **Failed Experiments:**
    *   **Liquidsoap:** Abandoned due to missing encoder support on Windows.
    *   **Named Pipes:** Originally used for FFmpeg communication but suffered stability issues on Windows.
    *   **Icecast Fallback:** A dedicated silence streamer was replaced by the current queue loop architecture.
*   **Inspiration:** The show *"Please be friendly"* is a homage to the discontinued Ö3 show of the same name.
