# Radio Würmchen - Vision and Architecture

## 1. Vision: AI-Curated, Human-Vetted Radio

**Goal:** To create a fully autonomous, AI-curated radio station that sounds professionally produced, providing a seamless mix of music and dynamically generated content (e.g., announcements, news, weather).

**Key Differentiator:** Full control over the AI's content and logic, with the ability for manual intervention and oversight by Kurt.

## 2. Architecture Overview

The system is built on a standard internet radio stack, with OpenClaw (the AI Agent) handling the **Intelligence Layer** by generating playlists, announcements, and scheduling.

| Layer | Component(s) | Role |
| :--- | :--- | :--- |
| **Storage** | `E:/Daten/Radio Würmchen/Musik` | Kurt's master music library. |
| **Intelligence** | OpenClaw Agent (`generate_playlist.py`, etc.) | Creates curated playlists, generates scripts for announcements, and schedules content. **(Future Work: Google Search/Web Scraping for dynamic info)** |
| **Automation** | Liquidsoap (`stream.liq`) | The stream engine. It reads the playlist, mixes music with announcements, and pushes the stream. |
| **Distribution** | Icecast Server | The broadcast tower. Accepts the Liquidsoap stream and makes it available to listeners at `http://localhost:8000/radio.mp3` (or `.ogg`). |

## 3. Component Deep Dive

### Liquidsoap (`stream.liq`)

The script is responsible for the flow of the broadcast.

*   **Current State (Minimal):** Currently configured to only stream the main music playlist to confirm connectivity.
*   **Original Goal (Mixing):** The original plan was to use a sequence mixer (`insert_dynamic` or similar) to alternate:
    *   **Music:** From the AI-generated `music.playlist`.
    *   **Announcements:** From a single file (`announcer/announcement.mp3`) that the AI can overwrite with new content (e.g., a voice-synthesized weather report).
*   **Output:** Configured to push a high-quality (192kbps) stream to Icecast.

### Playlist Generator (`generate_playlist.py`)

*   **Role:** This Python script reads music tags/metadata and uses AI logic to generate a dynamic, curated list of absolute file paths.
*   **Output:** The file `radio-wuermchen/music.playlist`.

## 4. Current Blockers (As of 2026-02-08, 19:40 GMT+1)

The entire system is blocked on getting a stable Liquidsoap installation that supports all the necessary audio formats.

*   **Status:** User is currently installing `git`, `make`, and `ffmpeg` via `pacman` in the MinGW 64-bit terminal to prepare for a successful source build.

---
*Created by Sidestepper 🦀 to document the project vision.*
