# AI Radio Station Project Specification: radio-wuermchen

## 0. Current State (Point of Failure)

**Status:** The system is currently non-operational.
**Observed Error:** Running `run_streamer.bat` results in an immediate failure of the FFmpeg pipe chain.
**Error Message:** `Der Befehl "C:" ist entweder falsch geschrieben oder konnte nicht gefunden werden.` (The command "C:" is either misspelled or could not be found.)
**Conclusion:** The batch script needs immediate debugging to resolve path or quoting issues before any further development on the Python script or AI logic can proceed.

---

This document serves as the foundational specification and constraint list for the AI Radio Station project, designed to prevent drift and re-work on known failures.

## 1. Logical Requirements (The "What")

### 1.1 Core Vision
Create a continuous, dynamic, Internet-reachable radio stream with a unique AI DJ persona that provides witty, resourceful, and dependable announcing and content. The station must operate autonomously without manual intervention.

### 1.2 DJ Persona & Content
- **Vibe:** Resourceful, witty, and dependable (matching Sidestepper's SOUL.md).
- **Tone Constraint:** **Must avoid "technobabble"** (e.g., calling humans "high performance units," or overusing words like "structural").
- **Show Structure:** Must implement a schedule of different, themed shows (e.g., news, tech, music production, history) that air at specific times.
- **Content:** The DJ must be able to:
    - Query the Internet for news relevant to the current show theme (e.g., tech news for a tech show).
    - Summarize this content and integrate it into the announcement breaks.
    - Select music adaptively based on the show, fetched content, and (eventually) listener taste/ratings.
    - Handle listener requests (future feature).

### 1.3 Music and Playback
- **Library:** Uses the local collection of 20,000+ MP3 files.
- **Playback:** Must achieve seamless, gapless playback between segments (announcement + song).
- **Playback Integrity:** The streaming script must contain a fallback mechanism (e.g., play a default jingle or short loop) to ensure the continuous stream **never breaks** even if the AI DJ fails to return a valid track file path.
- **Song Search Fallback:** If a specific song chosen by the DJ is not found in the library, the system must attempt to find **any** available track by the same artist before resorting to a random track or failing.
- **Wishlist Management:** The system must maintain a persistent **Wishlist File** (e.g., `wishlist.txt`) that is automatically populated whenever the AI DJ selects an unavailable track or a listener requests a track not found in the library.

### 1.4 DJ Polling Mechanism (Future Focus)
- **Efficiency Constraint:** The system requires a low-token, efficient, and robust method for triggering the AI DJ turn.
- **Options to Explore:** Investigate the proper use of OpenClaw's `sessions_spawn` for isolated, on-demand DJ turns, or utilizing an entirely independent external LLM/service.

## 2. Technical Requirements & Constraints (The "How")

### 2.1 Environment
- **Platform:** Windows 10 PC (prone to I/O/pipe issues).
- **Tooling:** Icecast (for distribution), Python scripts, FFmpeg, Windows PowerShell TTS.

### 2.2 Stable Streaming Architecture (MANDATORY)
The only successful continuous streaming method found so far is the **Named Pipe (FIFO) Chain**. This architecture must be maintained:
1.  **Batch Script (`run_streamer.bat`):** Must start Icecast and then a single, persistent FFmpeg **reader** process that consumes raw MP3 data from its standard input (`-i -`) and streams it to Icecast.
2.  **Python Script (`radio_streamer.py`):** Must run a loop that uses `subprocess.run` (or equivalent) to run an FFmpeg **writer** process. This writer process concatenates the necessary segments (`announcer.mp3` + `track.mp3`) and pipes the final raw MP3 output directly to the persistent FFmpeg reader's standard input.
3.  **Icecast Mountpoint:** Must stream to `/stream` (the mountpoint that was confirmed to work with this pipe chain).

### 2.3 Stable TTS Generation (MANDATORY)
- **Current Stable Engine:** Use the internal Windows text-to-speech tools via a PowerShell command integrated into the Python script for on-the-fly speech generation. This is the **baseline for stability.**
- **Future Exploration:** The goal is to find higher-quality TTS options. This includes investigating external provider models (e.g., Google/Anthropic) or superior local downloadable models.
- **Process:** The LLM generates the text, the Python script uses the chosen method (currently PowerShell) to convert the text to a temporary `announcer.mp3` file, and this file is then used in the concat-stream.

## 3. Lessons Learned / Stable Components (The "Do Not Touch" List)

The following components and decisions are considered stable or established constraints. **Do not attempt to revert to methods listed as failures.**

| Status | Component/Method | Constraint |
| :--- | :--- | :--- |
| **STABLE** | Continuous Streaming | **The Named Pipe / FFmpeg Chain to `/stream` is the working method.** |
| **STABLE** | TTS Output | **On-the-fly generation via PowerShell command is working.** |
| **FAILED** | Liquidsoap | **Do not attempt to use or debug Liquidsoap.** The Windows build lacks necessary encoders. |
| **FAILED** | Single-Segment Streamer | Reverting to the old `radio_streamer.py` that connected/disconnected for each track breaks continuity. |
| **FAILED** | Icecast Admin API Relay | The Zero-Downtime Handover method failed and is overly complex for the Windows environment. **Do not use the Icecast Admin API for source switching.** |
| **FAILED** | "Mega Concat" | Pre-concatenating full playlists prevents dynamic changes and causes buffer issues. |
| **CONSTRAINT** | Icecast Configuration | Any changes to `icecast.xml` must be handled with extreme care and documented before applying. |