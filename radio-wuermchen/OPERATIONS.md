# Radio Würmchen — Operations Manual

Everything you need to start, stop, and manage the station and its tools.

All Python commands use: `"C:\Program Files\Python311\python.exe"` (aliased as `python` below for readability).

Working directory for all commands: `C:\Users\kurt_\.openclaw\workspace\radio-wuermchen`

---

## 1. Starting the Station

The station requires **5 processes** running simultaneously, each in its own terminal window. Start them in this order:

### Step 1: Icecast (Broadcast Server)

Already handled by the streamer batch file (Step 2), which auto-starts Icecast. If you need to start it manually:

```
cd "C:\Program Files\Icecast"
icecast.bat
```

- Runs on **port 8000**
- Config: `C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\icecast.xml`
- To copy updated config: `copy_icecast_config.bat`

### Step 2: Streamer (Audio Pipeline)

```
run_streamer_queue.bat
```

- Starts Icecast automatically, then launches `streamer.py` piped through FFmpeg to Icecast
- Stream URL: `http://localhost:8000/stream`
- Log: `streamer.log`
- Creates `queue_low.signal` when the queue drops to ≤2 items (triggers the orchestrator)

### Step 3: DJ Orchestrator (Brain)

```
python dj_orchestrator.py
```

- The central intelligence — watches for `queue_low.signal`, calls the DJ Brain, manages shows, queues tracks
- Log: `orchestrator.log`
- **Must have `GEMINI_API_KEY` environment variable set** for LLM calls
- Polls every 3 seconds

### Step 4: Listener Server (Website + Player)

```
python listener_server.py
```

- Web interface on **port 8001**: `http://localhost:8001`
- Embedded audio player, now playing, listener requests
- Proxies the Icecast stream at `/stream`

### Step 5: External Access (ngrok Tunnel)

```
start_external_stream.bat
```

- Starts both the listener server AND ngrok tunnel
- Displays the public URL after startup
- Alternative: start ngrok manually: `ngrok http 8001`

### Quick Start (All at Once)

1. Run `run_streamer_queue.bat` (terminal 1)
2. Wait 5 seconds
3. Run `python dj_orchestrator.py` (terminal 2)
4. Run `start_external_stream.bat` (terminal 3 — includes listener server + ngrok)

---

## 2. Stopping the Station

- Close the terminal windows, or:
- `taskkill /F /IM python.exe` — kills all Python processes
- `taskkill /F /IM ngrok.exe` — kills ngrok
- Icecast: close its terminal window or `taskkill /F /IM icecast.exe`

---

## 3. Management Tools

### Show Schedule Editor (GUI)

```
python show_editor.py
```

- Opens automatically in browser at **http://localhost:8080**
- **3 tabs** accessible via navigation at the top:
  - **Shows** (`/`) — edit show schedule (times, music style, DJ personality, pools, signation, news toggle). Drag to reorder. Shows gap/overlap warnings.
  - **Track Aliases** (`/aliases`) — map DJ suggestions to actual filenames
  - **Wishlist** (`/wishlist`) — manage tracks the DJ wanted but weren't in the library. Click "Sync" to import new entries from `wishlist.txt`. Sortable columns, filterable by status.
- **Save** writes valid JSON every time — no more manual comma errors
- The orchestrator picks up changes on its next cycle (no restart needed)

### DJ Report (Song Analysis)

```
python dj_report.py --from "2026-02-22 06:00" --to "2026-02-22 09:00"
python dj_report.py --show "Good morning Vienna!"
python dj_report.py --from "2026-02-21 20:00" --to "2026-02-22" --show "blessings"
python dj_report.py
```

| Parameter | Description |
|-----------|-------------|
| `--from` | Start time (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`) |
| `--to` | End time (same format) |
| `--show` | Filter by show name (partial match, case-insensitive) |
| `--log` | Path to orchestrator.log (default: auto-detected) |
| *(none)* | Full log, all shows (prints usage hint) |

**Output sections:**
1. **DJ's own suggestions** — tracks the DJ came up with independently, ranked by frequency. Rating 22–40.
2. **Pool picks** — tracks chosen from the suggestion pool, ranked by offering frequency. Rating 21.
3. **Offered but not picked** — pool tracks the DJ ignored, ranked by offering frequency. Rating 0–19.

All entries include a **rating suggestion** (0–40 scale, average = 20).

### Pool Auto-Refill (LLM Classification)

```
python pool_refill.py                        # Dry run: classify 50 random tracks
python pool_refill.py --apply                # Classify and write to pool files
python pool_refill.py --rounds 5 --apply     # 5 rounds of 50 = 250 tracks
python pool_refill.py --batch-size 30        # 30 tracks per LLM call
python pool_refill.py --seed 42              # Reproducible selection
```

| Parameter | Description |
|-----------|-------------|
| `--apply` | Actually write to pool files (default: dry run) |
| `--rounds N` | Number of batches to process (default: 1) |
| `--batch-size N` | Tracks per LLM call (default: 50) |
| `--seed N` | Random seed for reproducible runs |

- **Requires `GEMINI_API_KEY` environment variable**
- Reads unassigned tracks from `music.playlist`, sends batches to Gemini Flash for classification into shows
- Tracks that don't fit any show go to the default pool (`suggestion_pool_curated.txt`)
- Auto-detects pool file encoding (UTF-8 vs ANSI/Latin-1)
- Log: `pool_refill_log.json` — previously classified tracks are skipped in future runs
- **Tip:** Run `--rounds 10` a few times over several days to process the ~9,600 unassigned tracks

### Playlist Generator

```
python generate_playlist.py
```

- Scans `E:\Daten\Radio Würmchen\Musik` recursively
- Outputs `music.playlist` (absolute paths, one per line)
- **Run after adding new music to the library**

### Pool Generator

```
python generate_pools.py
```

- Regenerates suggestion pools from `music.playlist` based on artist/keyword filters
- Overwrites `suggestion_pool_*.txt` files
- **Note:** Some pools are now curated (`*_curated.txt`) — these are NOT overwritten by this script

### Charts Scraper

```
python charts_scraper.py
```

- Scrapes austriancharts.at (Top 75 singles)
- Matches against library → `charts_in_library.json`
- Auto-triggered daily by the orchestrator (no manual run needed normally)

---

## 4. Configuration Files

| File | What it controls | Edited via |
|------|-----------------|------------|
| `shows_schedule.json` | Show times, styles, pools, defaults | Show Editor GUI |
| `track_aliases.json` | DJ suggestion → filename mapping | Aliases Editor GUI |
| `dj_config.json` | Gemini model, DJ name, language | Text editor |
| `icecast.xml` | Icecast server settings | Text editor |
| `tts_config.json` | TTS voice and engine settings | Text editor |

### Environment Variables

| Variable | Required by | Description |
|----------|------------|-------------|
| `GEMINI_API_KEY` | `dj_orchestrator.py`, `pool_refill.py` | Google Gemini API key |

---

## 5. Log Files

| File | Content |
|------|---------|
| `orchestrator.log` | Main log — DJ cycles, show transitions, track matching, errors |
| `streamer.log` | Audio pipeline — tracks streamed, queue status |
| `listener_requests.log` | Incoming listener requests |
| `pool_refill_log.json` | Pool auto-refill classification history |
| `dj_debug.log` | DJ Brain stderr output (debugging) |

---

## 6. Key Data Files

| File | Purpose | Modified by |
|------|---------|-------------|
| `queue.txt` | Active playback queue | Orchestrator (write), Streamer (read/consume) |
| `queue_low.signal` | Triggers orchestrator | Streamer (create), Orchestrator (delete) |
| `dj_request.json` | Context sent to DJ Brain | Orchestrator |
| `dj_response.json` | DJ Brain response | DJ Brain |
| `dj_history.json` | Last 50 tracks (repeat prevention) | Orchestrator |
| `music.playlist` | Full library listing | `generate_playlist.py` |
| `wishlist.txt` | Tracks DJ wanted but weren't found | Orchestrator |
| `wishlist_db.json` | Wishlist tracking database | Show Editor |
| `news_cache.json` | Cached orf.at stories (60min TTL) | News Manager |
| `news_state.json` | Presented story tracking | News Scheduler |
| `charts_cache.json` | Cached chart data | Charts Scraper |

---

## 7. Troubleshooting

**No sound / stream offline:**
- Check if Icecast is running (http://localhost:8000)
- Check if `streamer.py` is running and `streamer.log` shows activity
- Check `queue.txt` — is it empty?

**DJ not picking songs:**
- Check `GEMINI_API_KEY` is set
- Check `orchestrator.log` for errors (API errors, rate limits)
- In power-save mode (no listeners), LLM is skipped — songs come from pools only

**Wrong song version matched:**
- Add an alias in Track Aliases editor (http://localhost:8080/aliases)
- The raw match requires exact filename match; aliases handle fuzzy cases

**Show not transitioning:**
- Check `shows_schedule.json` for valid JSON (use the Show Editor!)
- Check for time gaps in the schedule (editor shows warnings)

**TTS not working:**
- Check `tts_rate_limit.warn` — if present, Gemini TTS hit rate limit (1hr cooldown)
- Falls back to Windows SAPI voices automatically

**Pool refill encoding issues:**
- The script auto-detects encoding per file; if a pool file looks garbled, check if it was saved with mixed encodings
