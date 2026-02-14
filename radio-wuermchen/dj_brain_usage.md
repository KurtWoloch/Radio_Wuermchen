# DJ Brain Subsystem Documentation

This module encapsulates the AI DJ logic, designed to run completely independently of the main OpenClaw session via a dedicated Python script (`dj_brain.py`) that communicates using file I/O. This allows for swappable LLM providers (currently Google Gemini) without affecting the core streamer.

## Execution Flow

The DJ system is intended to be triggered by the `queue_filler.py` script when the music queue runs low:

1.  **Trigger:** `queue_filler.py` detects low queue and writes context to `dj_request.json`.
2.  **Execution:** `queue_filler.py` executes `python dj_brain.py`.
3.  **LLM Call:** `dj_brain.py` reads configuration, builds the prompt, calls the configured LLM (via Google or Anthropic API), and waits for a response.
4.  **Response:** The LLM output is saved as JSON to `dj_response.json`.
5.  **Action:** `queue_filler.py` reads `dj_response.json`, generates announcement audio via `tts_generate.py`, and pushes both the announcement and the new song to `queue.txt`.
6.  **Memory:** `dj_brain.py` updates `dj_history.json` with the new track selection.

## Interfacing Files

The DJ brain relies on four key files located in the project directory:

### 1. `dj_config.json` (Configuration)
*   **Purpose:** Stores LLM credentials and personality defaults.
*   **Structure:**
    ```json
    {
        "provider": "google" | "anthropic",
        "model": "gemini-2.5-flash-preview-04-17" | "anthropic/claude-3-5-sonnet",
        "api_key": "YOUR_API_KEY_HERE",
        "dj_name": "DJ Flash",
        "station_name": "Radio Würmchen",
        "language": "English"
    }
    ```
*   **Action:** **Must be updated** with your Google API key to enable Gemini connection.

### 2. `dj_request.json` (Input Context)
*   **Purpose:** Provides the DJ with the current context to make an informed decision. Written by the calling script (e.g., `queue_filler.py`).
*   **Structure:**
    ```json
    {
      "last_track": "Artist - Title of the track that just finished",
      "listener_input": "Optional text from a listener request or comment (null if none)",
      "instructions": "Optional high-priority instruction (null if none)"
    }
    ```

### 3. `dj_response.json` (Output Decision)
*   **Purpose:** Where the DJ script writes its final decision. Read by the calling script.
*   **Structure:**
    ```json
    {
      "track": "Artist - Title for the NEXT song suggestion",
      "announcement": "The spoken DJ intro/transition text"
    }
    ```
*   *Note: If the LLM fails to respond correctly, this file will contain an "error" key.*

### 4. `dj_history.json` (DJ Memory)
*   **Purpose:** Provides the DJ with short-term memory (last 10 plays) to ensure variety and avoid immediate repetition.
*   **Structure:** A JSON array of objects containing only the tracks selected by the DJ.

This separation makes the DJ a fully encapsulated, swappable agent.