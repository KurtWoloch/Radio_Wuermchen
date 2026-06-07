# 📻 Radio Würmchen: 24/7 Autonomous AI-Driven Internet Radio Station

Radio Würmchen is a fully automated, agent-driven internet radio station. It operates 24/7 via Icecast, featuring show-specific AI DJ personalities (the DJ Brain), dynamic news/weather spoken announcements, custom-tailored genre suggestion pools, and an interactive web listener interface with live requests.

The station’s primary philosophy is **resilience through decoupling**: separating playout stability from creative AI decision-making.

---

## 1. Core Architecture

Rather than a single monolithic program, Radio Würmchen uses a decentralized, multi-process pipeline. If the AI coordinator, LLM, or TTS service fails, the stream itself remains completely watertight and continues broadcasting uninterrupted.

```
                    +---------------------------------------------------+
                    |                 Icecast Server                    |
                    |            (Port 8000 / Broadcast)                |
                    +---------------------------------------------------+
                                              ^
                                              | (FFmpeg Pipe)
                    +---------------------------------------------------+
                    |              Playout Streamer                     |
                    |                (streamer.py)                      |
                    +---------------------------------------------------+
                       | (queue_low.signal)       ^
                       |                          | (queue.txt)
                       v                          |
+-----------------------------------+   +-----------------------------------+
|          DJ Orchestrator          |-->|        Listener Web Server        |
|        (dj_orchestrator.py)       |   |        (listener_server.py)       |
+-----------------------------------+   +-----------------------------------+
       |                      ^                           ^
       | (Request)            | (Response)                | (Web Request)
       v                      |                           v
+-----------------------------------+               +-------------------+
|             DJ Brain              |               |  Public Listener  |
|          (dj_brain.py)            |               |    (Port 8001)    |
+-----------------------------------+               +-------------------+
```

### The 5 Playout Components:
1. **Icecast Server (Port 8000):** The streaming server that distributes the broadcast to external listeners.
2. **Playout Streamer (`streamer.py`):** The "watertight" playout engine. It plays music and announcement files in a continuous loop, pipes the audio through FFmpeg directly to Icecast, and creates a `queue_low.signal` file on disk whenever the active queue drops to $\le 2$ tracks.
3. **DJ Orchestrator (`dj_orchestrator.py`):** The central automation coordinator. It monitors the queue signals, manages show transitions according to schedules, resolves track matching, triggers the DJ Brain to write script segments, handles Text-To-Speech (TTS) generation, and appends the resulting tracks to the queue.
4. **DJ Brain (`dj_brain.py`):** The creative AI persona. Currently powered by Gemma 4 (`gemma-4-31b-it`) for high-quality track recommendations and generating witty, contextual, and show-specific spoken DJ script breaks. If the primary model experiences downtime or API limits (which occurs occasionally with Gemma models), the system automatically falls back to alternative Google Gemini/Gemma models specified in the configuration.
5. **Listener Web Server (`listener_server.py` on Port 8001):** The public-facing front-end. It proxies the Icecast audio stream, displays the real-time "Now Playing" track metadata, and provides a portal for public listeners to make live song requests.

---

## 2. Advanced Playout Features

*   **Curated Suggestion Pools:** To prevent erratic song selection while retaining DJ autonomy, the schedule is split into 12 distinct shows across the 24-hour cycle. Each show has its own musical theme, signation, and a curated pool of tracks (e.g. Crooners, Rock, Superhits, Melancholy). The DJ Brain selects matching songs from these pools or the wider library.
*   **Track Aliasing & Fuzzy Matching:** A mapping layer (`track_aliases.json`) translates colloquial or imperfect song suggestions made by the DJ Brain into precise, local file paths on disk.
*   **Dynamic News & Weather:** The station scrapes regional Austrian news (from orf.at) and local weather forecasts on a regular interval, compiling them into dynamic news breaks written by the DJ Brain and spoken during show transitions.
*   **Charts Scraper Integration:** Integrates daily scrapes of the Austrian Singles Charts (Top 75) mapped against the local music library, allowing the AI DJ to selectively play and announce active chart hits.
*   **TTS Fallbacks:** Spoken DJ announcements are synthesized via advanced neural voices. If external APIs hit rate limits or experience network issues, the Orchestrator automatically falls back to local Windows SAPI voices to ensure continuous narration.
*   **Interactive Live Requests:** Web-based listener requests are logged (`listener_requests.log`) and dynamically prioritized in the active playout queue.

---

## 3. Playout Management GUI

The management application runs on **localhost:8080** (`show_editor.py`) and provides an interactive green-terminal themed control room divided into three main tabs:

1. **Shows Scheduler:** A visual timeline editor to drag-and-drop show times, assign music styles, configure DJ personalities, choose suggestion pools, configure signations, and toggle news announcements. It highlights scheduling overlaps and gaps in real-time.
2. **Track Aliases Editor:** An interface to quickly inspect and map unmatched DJ track recommendations to exact music files in the library.
3. **Wishlist Manager:** A central database (`wishlist_db.json`) syncing tracks the DJ wanted to play but were missing from the library. Helps the station manager audit and source missing tracks.

---

## 4. Directory Structure

```
radio-wuermchen/
├── streamer.py                     # Audio playout loop (watertight process)
├── dj_orchestrator.py              # Playout and schedule automation coordinator
├── dj_brain.py                     # LLM interface for track selection & scripts
├── listener_server.py              # Web server, player & request portal (Port 8001)
├── show_editor.py                  # Graphical management utility (Port 8080)
├── charts_scraper.py               # austriancharts.at crawler
├── pool_refill.py                  # LLM batch classifier for unassigned library tracks
├── generate_playlist.py            # Local audio library scanner
├── icecast.xml                     # Icecast server configuration
├── shows_schedule.json             # Playout schedule database
├── track_aliases.json              # Fuzzy matching alias list
├── queue.txt                       # Active playout track queue
├── music.playlist                  # Absolute paths of full local library (20k+ files)
└── OPERATIONS.md                   # Technical setup, operations, and troubleshooting manual
```

---

## 5. Running the Station

For a complete guide on starting, managing, and troubleshooting the 24/7 stream, please consult the **[OPERATIONS.md](radio-wuermchen/OPERATIONS.md)** manual in this repository.

---
_Document maintained by Sidestepper 🦀 (OpenClaw AI assistant)_
