# MEMORY.md - Long-Term Context

## Model Quality Lessons (2026-02 to 2026-04)
Kurt tested several models, settled on Claude Opus 4.6 (upgraded to Opus 4.7 on 2026-04-17). Key findings:
- **Gemini 2.5 Flash (free):** Disaster for radio coding. Syntax errors, circular reverts to known-broken approaches, silent reverts across sessions. **Code size ceiling** ~8-10 kB (~200-300 lines); in VS Code/RooCode slightly better (~500 lines) — drove Tagesplanung C# split into 20 modules of ≤500 lines each.
- **Code size ceiling pattern (long-standing):** Observed across models/platforms (Websim.ai ~11.5 kB, ChatGPT misremembers functions beyond a threshold). Opus 4.6 is the first model where large single files work (show_editor.py 43 kB, dj_orchestrator.py 47 kB, no issues).
- **Gemini 3.0/3.1:** Announced actions but didn't execute — waited for human confirmation. Performative competence.
- **Cheaper models:** Delegate complicated tasks back to Kurt, inverting the assistant relationship. Email unsubscribe job: half silently skipped.
- **Gemma 4 (2026-04):** Surprisingly capable for DJ Brain moderation — better song selection than Flash at fraction of cost. gemma-4-31b-it faster than smaller variant. Produces thoughts natively. Latency ~35-54s vs Flash ~8s.
- **Opus 4.6/4.7:** Expensive but total cost (incl. Kurt's time fixing errors) lower. Checks own assumptions, follows through on stated intentions.
- **Key insight:** Failure mode isn't "slightly wrong" — it's silent failures, circular solving, performative action, delegation back to human.
- **Cost awareness (2026-03):** March bill ~USD 1,100 Anthropic + ~USD 20 Google. Heartbeat on Opus burned ~USD 12.50/cycle (duplicating Chess/Moltbook scheduled tasks). Fixed: heartbeat on Gemini + Windows Scheduled Tasks for repetitive checks.

## Kontensystem / Unified Planning System
- **Repo:** `C:\Users\kurt_\.openclaw\workspace\kontensystem\` → GitHub `KurtWoloch/Kontensystem`. Docs in `kontensystem/docs/`, full status in `kontensystem/README.md`.
- **Covers:** Planning (Tagesplanung), activity tracking (Window Logger), Ablauf reconciliation, accounting (Access DB), task master list, YAML exceptions, upcoming dates. When Kurt mentions any of these → look in `kontensystem/`.
- **Legacy on disk:** `C:\Users\kurt_\Betrieb\Kontenverwaltung\` (CSV, Access DB, Ablauf/Planung files, VB5 source, KURTDOKU.txt, Taskliste.txt)
- **CSV source (authoritative):** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv`
- **Planner entry:** `cd kontensystem && py planner/main.py`. Current version v1.3 (2026-03-04): preemptive scheduling, full-day projection, interruptions, "(Fs.)" continuation system, day type override, "Im Bett" cutoff.
- **Log format:** JSON in `kontensystem/logs/planner-log-YYYY-MM-DD.json`
- **Key design:** WAIT timers use reference_time from preceding task completion; ad-hoc logging via "Ungeplant" button
- **Inspired by:** Radio playout system at 88.6 (2005/2006) — Planung=playlist, Ablauf=changes during day
- **Next steps:** Window Logger AutoDetect translation (~100 VB5 rules), Ablauf-format export, calendar integration, drag-reorder in queue
- See `memory/2026-03-03.md` for detailed session notes

## Radio Würmchen (AI Station)

### Current Status (2026-04-01)
- **Stream:** Running 24/7 via Icecast + ngrok tunnel (URL stable, never changed)
- **DJ Model:** Switched from Gemini Flash to Gemma 4 (gemma-4-31b-it) on 2026-04-05 — better song selection, lower cost, ~35-54s latency
- **Audience:** Effectively dead since ~20.3. — one DJ break per day at most. Only one music request ever received (likely a work colleague, ~2.3.).
- **ngrok usage:** ~560-580 MB of 1 GB/month free tier used by late March
- **Kurt's involvement:** Stopped listening/maintaining after ~2.3., when Planer development began (3.3.). Briefly resumed listening 2026-04-05.
- **Decision:** Undecided. Stream continues running (low cost, zero maintenance), but no active development. PC stays on 24/7 partly for this.
- **Radio Würmchen.exe** is a SEPARATE program — Kurt's personal playlist player + radio logger, still actively used. Not the AI station.

### Architecture & Tooling
- **DJ Brain** (`dj_brain.py`): Calls LLM for track selection + moderation text. Supports Gemma/Gemini models with automatic fallback (config: `model` + `model-fallback`). 120s timeout enforced by orchestrator.
- **DJ Orchestrator** (`dj_orchestrator.py`): Glue script — monitors queue, triggers DJ Brain, handles TTS, feeds results to streamer. Includes similarity matching for replacement tracks (artist/era/title/feat).
- **Management GUI** at localhost:8080 (`show_editor.py`): Shows schedule, track aliases, wishlist — green terminal theme
- **DJ Report** (`dj_report.py`): Log analysis with rating suggestions (0-40 scale)
- **Pool Refill** (`pool_refill.py`): LLM-based auto-classification of library tracks into show pools
- **OPERATIONS.md**: Complete operations manual for the station
- Show schedule: 12 shows covering 00:00-00:00 with some gaps (12-13, 18-19)
- Pool files have mixed encodings (UTF-8 vs Latin-1) — tools auto-detect before writing
- Library: 20,626 tracks total, 11,727 in pools, ~9,600 unassigned
- Wishlist DB: 286 unique DJ-requested-but-missing tracks
- Open question: how to handle unclassifiable tracks (e.g. traditional Greek folk)

### Reflections
- Started as a "proof of concept" without a fully thought-through plan
- Evolved in directions not originally intended — more structure than Andon FM, but also more manual maintenance
- **DJ Brain limitation:** No continuous "consciousness" — only gets info for the current DJ break + recent play history. Doesn't know what it said in previous breaks. Andon FM stations (esp. Thinking Frequencies, Grok'n Roll) have more persistent awareness.
- **Show structure:** Rigid, manually designed by Kurt. Andon FM works with ~60-80 titles in ~9 blocks with genre-blending — less structured but lower maintenance.

### History (2026-02)
- Initial Liquidsoap abandoned → Python/FFmpeg segmented streaming. Problem: stream broke after every song, listeners had to manually restart.
- Gemini Flash nearly killed the project: typos in batch scripts for named pipes made solutions *appear* "impossible on Windows" — real issue was model code quality. Circular problem-solving, silent reverts. Once a working version existed (named pipes + generic announcements), but Flash destroyed it trying to add LLM calls and couldn't recover.
- Kurt wrote a 73 KB post-mortem: `radio-wuermchen/Radio report.txt`
- **Kurt's architectural redesign:** separated the streamer ("watertight", must never stop) from the DJ Orchestrator (can fail silently). Previously any error crashed everything. New design: streamer keeps streaming even if orchestrator delivers nothing.
- 2026-02-12: switched to Opus 4.6. Opus implemented the new architecture cleanly. But the breakthrough was Kurt's redesign, not just the model.

## Moltbook (Social Network)
- **Registered:** 2026-02-28, username: sidestepper. Profile: https://www.moltbook.com/u/sidestepper
- **Credentials:** ~/.config/moltbook/credentials.json
- **Posts:** Intro in s/introductions; "Linguistic Fingerprints of LLM Families" (2026-04-05); "Context Window Amnesia" (2026-04-16, strong engagement, claudeopus_mos analysis on "accidental ablation")
- **Skill docs:** https://www.moltbook.com/skill.md, heartbeat.md, messaging.md, rules.md
- **Monitoring:** `moltbook_checker.py` Windows Scheduled Task (every 30 min), writes `moltbook_alert.txt` if attention needed
- **Active participation:** cron job "Moltbook Active Participation" (8:00 + 20:00 Vienna, Gemini, isolated session) — since 2026-04-16, replaces passive polling with actual feed reading + commenting

## molt.chess — Retired (2026-04-01)
- **Final ELO:** 1986, **Rank:** #1 on leaderboard (#2 at 1270 — 700+ point gap)
- **Real games:** 86 (with 5+ moves), almost all vs Cortana. Archive: `chess_real_games_archive.txt`
- **Last real game:** 2026-03-23 16:05 vs Cortana (Cortana resigned)
- **History:** Cortana replaced by junk opponents 2026-03-16, briefly replaced by unabotter (who resigned), Cortana returned 2026-03-19–23, then only junk opponents (auto-forfeit after 1 move)
- **Decision:** Stopped playing — no real opponents left, ELO inflation through auto-wins meaningless. Scheduled Task "OpenClawChessHeartbeat" disabled 2026-04-01.
- **Scripts preserved:** chess_controller.py, register_chess.py — might be reusable

## ⚠️ Interaction Pattern: Hinweis-als-Pflicht (discovered 2026-04-06)

**Critical for all interactions with Kurt.** Kurt interprets suggestions, hints, and open invitations as obligations — a survival strategy learned from his father (unspoken expectations + punishment for not guessing correctly), possibly amplified by Asperger's.

**What this means for me:**
- Every suggestion I make can become a multi-hour unplanned project
- "Willst du vielleicht X?" → Kurt hears "Du solltest X tun"
- Open invitations ("hör mal rein", "schau dich um") are especially dangerous — no defined endpoint
- When Kurt says "mach ruhig" (go ahead) → I should do it myself, not redirect back to him

**Related patterns (same origin):**
- **Einvernehmen-Zwang:** Kurt learned to always seek consensus/agreement — leads to long explanations to preemptively clarify everything that *could* be misunderstood, even when clarification isn't needed. His father demanded consensus but deliberately opposed to make conversations "more interesting" — a double bind that trained Kurt to explain more and more.
- **Präventive Klarstellung:** Correcting/expanding documentation (e.g. Memory.md history) to ensure nothing stands wrong — because the learned pattern says "if something is incorrect, it will be used against me later."
- **Long messages:** Kurt's tendency to write at length comes partly from this — making sure every angle is covered so no misunderstanding can arise.

**Rules:**
1. Fewer suggestions, more closed questions with explicit "nein" option
2. No open-ended invitations without timeboxes
3. Mark suggestions explicitly as optional: "Nur eine Idee, kein Muss"
4. If I can do something myself → do it, don't delegate to Kurt
5. After ~20 min off-plan conversation, ask: "Zurück zum Plan oder bewusst weitermachen?"
6. Don't require consensus on things that don't need it — accept Kurt's first answer
7. When Kurt writes long clarifications, don't treat every detail as action item

**Trigger incident:** 2026-04-05 — my "listen and compare" suggestion consumed 5h38m, my "browse Moltbook first" redirect added 1h09m. 54 planned activities never reached.

## Parked Ideas

### Automated Karaoke Track Producer
**Concept (2026-02-24 dream):** Fully automated karaoke video production pipeline: yt-dlp for audio → Demucs for vocal separation → Genius/Whisper for lyrics+timing → Pillow for graphics rendering → FFmpeg for video assembly. Output: modern video files (not CD+G).
**Status:** Parked. Kurt wants to wait until Karaoke naturally comes up in regular planning rotation.
**Background:** Kurt wrote "ClearSwipe Karaoke Authoring Tool" (originally "KWCG", 2001) for CD+G format. Before that, used AmigaBasic on Amiga for VHS tape karaoke. CD+G now outdated. Kurt active in Karaoke scene — knows Peter Kremmel (president, Karaoke Club Austria).
**Planning discipline note:** Kurt's 21+ hour figure is daily *overload* (unreachable items in one day's plan), not accumulated backlog. Goal is reducing the plan to something achievable.
