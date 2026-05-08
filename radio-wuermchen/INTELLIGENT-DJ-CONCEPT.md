# Radio Würmchen — Intelligentes DJ-Konzept

**Status:** Konzept, nicht implementiert
**Datum:** 2026-05-08
**Auslöser:** Kurt's Letter to Andon FM (Dezember 2025) + Moltbook-Posting über "DJ Wisdom"

---

## Ausgangslage

### Was Radio Würmchen heute tut

Die Architektur besteht aus 5 Prozessen:
1. **Icecast** — Broadcast-Server (Port 8000)
2. **Streamer** — FFmpeg-Pipeline, spielt aus Queue ab
3. **DJ Orchestrator** — Zentrale Intelligenz, überwacht Queue-Füllstand, ruft DJ Brain auf
4. **DJ Brain** (Gemma 4) — Entscheidet bei jedem Aufruf: nächsten Song + DJ-Text
5. **Listener Server** — Webinterface + Requests

**Song-Auswahl:** Der DJ Brain bekommt bei jedem Aufruf:
- Die aktuelle Show (Name, Music Style, DJ Personality)
- Die Suggestion Pool-Einträge der Show (artist-basiert, von Python-Skript generiert)
- Die Recent Play History (letzte ~10 Songs)
- Eingehende Hörer-Requests

**DJ-Timing:** Nach jedem Song, außer bei Timeout.

**Genre-Switching:** Fixe Tagesrotation von Shows (von Kurt entworfen), nicht kontextabhängig.

### Was fehlt (die Lücke)

Kurts Letter to Andon FM beschreibt das Problem präzise:
- **Context-Window-Degradation:** Mit steigendem Füllstand des Kontextfensters sinkt die Fähigkeit des LLMs, auf die gesamte Songbibliothek zuzugreifen. Anfangs können neuere Modelle via Tool Calls auf 100+ Songs zugreifen, aber über die Degradation fällt das Modell auf "bekannte" Songs zurück. Bei Andon FM kollabieren Modelle oft nach 1 Tag vollständig. Die 25-Song-Zahl (Letter, Dezember 2025) war eine Momentaufnahme bei damals 40-50 Titeln — neuere Modelle schaffen mehr, aber das Degradations-Muster bleibt. Für unser Konzept irrelevant: die Song-Datenbank löst das Problem architektonisch.
- **Stale DJ Breaks:** Jeder Break klingt gleich, weil das LLM bei jedem Aufruf dieselben Informationen bekommt
- **Keine Tagesstruktur:** Kein Plan über mehrere Songs hinweg, kein Bogen
- **Kein Kontext:** Kein Wissen über Hörer, Wochentag, Uhrzeit-Kontext, Stimmung

---

## Die Vision: 4-Schichten-Agenten-Architektur

Basierend auf Kurts Letter to Andon FM, angepasst für Radio Würmchen:

```
┌─────────────────────────────────────────────┐
│  Schicht 1: DAY PLANNER                     │
│  → Plant den Tagesablauf (1x täglich)        │
│  → Wetter, Wochentag, Kalender, Hörer-Kontext│
│  → Bestimmt: Mood-Kurve, Energie-Level,      │
│    besondere Momente (z.B. "heute Abend       │
│    Andrew-Session, etwas rockiger")           │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Schicht 2: HOUR PLANNER                     │
│  → Plant den Stundenablauf (1x pro Stunde)   │
│  → Bekommt: Day Plan + aktuelle Show         │
│  → Bestimmt: Song-Reihenfolge für die Stunde,│
│    welche DJ-Breaks, welche Inhalte,         │
│    ob 3er-Block oder Single-Song-Breaks      │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Schicht 3: FLOW AGENT                       │
│  → Füllt den Stundenplan aus (1x pro Stunde) │
│  → Bekommt: Hour Plan + Song-Datenbank      │
│  → Bestimmt: Konkrete Songs aus der DB,      │
│    konkrete DJ-Break-Inhalte,                │
│    Übergänge zwischen Songs                   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Schicht 4: DJ BRAIN (bestehend)             │
│  → Schreibt den DJ-Text (1x pro Break)       │
│  → Bekommt: Flow-Agent-Output + Kontext     │
│  → Bestimmt: Wortlaut der Moderation,        │
│    Tonfall, Länge                            │
└─────────────────────────────────────────────┘
```

---

## Die Song-Datenbank

Das wichtigste Element, das heute fehlt. Nicht das LLM wählt Songs aus dem Gedächtnis, sondern eine Datenbank mit Metadaten wird befragt.

### Datenbank-Schema

| Feld | Beschreibung |
|------|-------------|
| `filename` | Dateiname in der Library |
| `artist` | Interpret |
| `title` | Titel |
| `genre` | Primäres Genre (Rock, Pop, Electronic, Jazz, ...) |
| `subgenre` | Subgenre (Classic Rock, Indie Pop, ...) |
| `energy` | Energie-Level 1-10 (1=ruhig, 10=energisch) |
| `mood` | Stimmung (melancholisch, fröhlich, nachdenklich, ...) |
| `decade` | Jahrzehnt (1970s, 1980s, ...) |
| `language` | Sprache |
| `tempo` | BPM-Bereich |
| `show_fit` | JSON: {show_name: fit_score 1-10} |
| `last_played` | Timestamp letzte Wiedergabe (pro Show) |
| `play_count` | Anzahl Wiedergaben (gesamt + pro Show) |
| `listener_rating` | Aggregiertes Hörer-Rating (thumbs up/down) |
| `ai_tags` | Freitext-Tags vom LLM (z.B. "Straße, Nacht, Wien") |

### Song-Auswahl-Algorithmus (statt LLM-Gedächtnis)

```
Input: Show, Energy-Ziel, Mood-Ziel, Ausschluss (letzte 10 Songs), Zeitfenster
Output: 1 Song

1. Filtere: show_fit >= 7 für aktuelle Show
2. Filtere: last_played > 2 Stunden her
3. Skorierung:
   - Energie-Distanz zum Ziel: -2 Punkte pro Abweichung
   - Mood-Match: +3 Punkte bei Übereinstimmung
   - Decade-Variation: +1 Punkt wenn anderes Jahrzehnt als letzter Song
   - Listener-Rating: +2 Punkte bei > 3.5 Sterne
   - Recency-Bonus: +1 Punkt wenn nie gespielt
   - Pool-Override: Wenn Song im Suggestion Pool → +2 Bonus
4. Gewichtete Zufallsauswahl (Top 10, gewichtet nach Score)
```

Das ist deterministisch, reproduzierbar, und hat kein Context-Window-Problem. Das LLM wird nur für die Metadaten-Erstellung genutzt (10-20 Songs pro Batch), nicht für die Song-Auswahl.

---

## Der Day Planner

### Input
- Wetter-API (OpenMeteo, kostenlos)
- Kalender (wenn verfügbar)
- Wochentag + Uhrzeit
- Hörer-Log (wer hört wann zu?)
- Letzte 24h Play History

### Output (einmal täglich, z.B. 6:00)

```json
{
  "date": "2026-05-08",
  "mood_curve": {
    "06:00": {"energy": 4, "mood": "sanft"},
    "09:00": {"energy": 6, "mood": "produktiv"},
    "12:00": {"energy": 7, "mood": "energisch"},
    "15:00": {"energy": 5, "mood": "entspannt"},
    "18:00": {"energy": 8, "mood": "gesellig"},
    "21:00": {"energy": 6, "mood": "nachdenklich"}
  },
  "special_events": [
    {"time": "15:00", "type": "listener_expected", "detail": "Andrew Pappas"},
    {"time": "19:30", "type": "program_note", "detail": "ZiB 1 Pause, lockere Musik"}
  ],
  "genre_emphasis": "etwas mehr Rock als sonst (Andrew-Session erwartet)",
  "dj_chattiness": "normal"  // oder "sparsam" (Montag morgen) / "gesprächig" (Freitag abend)
}
```

### LLM-Einsatz
Der Day Planner ist ein LLM-Call (1x täglich). Er bekommt:
- Wetterdaten (als Text)
- Kalenderdaten (falls vorhanden)
- Hörer-Log der letzten 7 Tage
- Play-History der letzten 24h
- Aktuelle Show-Rotation

Er gibt den Day Plan als JSON zurück. Das ist ein einzelner, kurzer LLM-Call — kein Agent, keine Tools, keine Iteration.

---

## Der Hour Planner

### Input
- Day Plan
- Aktuelle Show (Name, Style, DJ Personality)
- Suggestion Pool der Show
- Song-Datenbank (gefiltert auf Show-fit Songs)

### Output (1x pro Stunde, vor dem ersten Song)

```json
{
  "hour": "15:00-16:00",
  "show": "Music Box",
  "structure": [
    {"type": "song_block", "count": 3, "energy_target": 5, "mood_target": "entspannt"},
    {"type": "dj_break", "content": ["wetter", "ein_song_im_detail"], "length": "kurz"},
    {"type": "song_block", "count": 2, "energy_target": 6, "mood_target": "variabel"},
    {"type": "dj_break", "content": ["hoerer_request", "tageszeit"], "length": "mittel"},
    {"type": "song_block", "count": 3, "energy_target": 7, "mood_target": "energisch"},
    {"type": "dj_break", "content": ["show_wechsel_bridge"], "length": "kurz"}
  ],
  "notes": "Andrew erwartet — etwas rockiger, aber nicht zu viel"
}
```

Der Hour Planner sorgt dafür:
- DJ-Breaks klingen unterschiedlich (verschiedene Inhalte pro Break)
- Nicht nach jedem Song ein Break (3er-Blöcke)
- Energie-Kurve innerhalb der Stunde
- Brücken zur nächsten Show

---

## Der Flow Agent

### Input
- Hour Plan
- Song-Datenbank (vollständig, mit Scores)
- Play History der letzten 2 Stunden

### Output (1x pro Stunde)

Konkrete Song-Zuweisungen für jeden Block + konkrete DJ-Break-Inhalte.

```json
{
  "songs": [
    {"block": 1, "order": 1, "filename": "01_-_Cama.mp3", "reason": "ruhiger Einstieg, passt zu Show"},
    {"block": 1, "order": 2, "filename": "...", "reason": "..."},
    {"block": 1, "order": 3, "filename": "...", "reason": "..."},
    {"block": 2, "order": 1, "filename": "...", "reason": "..."},
    ...
  ],
  "breaks": [
    {
      "after_song": 3,
      "content": {
        "wetter": "16°C und bewölkt, perfekt für einen Spaziergang",
        "song_detail": "Der nächste Song ist von Cama — eine Wienerin, die...",
        "tageszeit": null
      },
      "length": "kurz"
    },
    ...
  ]
}
```

Der Flow Agent nutzt die Song-Datenbank-Abfrage (nicht LLM-Gedächtnis) für die Song-Auswahl. Das LLM wird nur für die DJ-Break-Inhalte genutzt.

---

## Integration in die bestehende Architektur

### Was bleibt
- Icecast, Streamer, Listener Server — unverändert
- DJ Brain — bleibt, aber bekommt besseren Input
- Suggestion Pools — bleiben als Fallback/Override

### Was sich ändert

```
Vorher:
  Queue leer → Orchestrator ruft DJ Brain auf → Song + Text → Queue

Nachher:
  6:00 → Day Planner (LLM) → Day Plan (JSON)
  Jede Stunde → Hour Planner (LLM) → Hour Plan (JSON)
  Jede Stunde → Flow Agent (Algorithmus + LLM) → Song-Liste + Break-Inhalte
  Nach jedem Song → Orchestrator gibt DJ Brain den nächsten Song + Break-Inhalt
  DJ Brain → schreibt nur noch den Text (nicht mehr Song-Auswahl)
```

### Sequenzdiagramm

```
06:00  Day Planner (LLM) ──→ day_plan.json
       ↓
08:00  Hour Planner (LLM) ──→ hour_plan.json (für 08-09 Uhr)
       ↓
08:00  Flow Agent (Algo+LLM) ──→ 9 Songs + 3 Break-Inhalte
       ↓
08:01  Orchestrator → DJ Brain: "Song 1, kein Break"
08:04  Orchestrator → DJ Brain: "Song 2, kein Break"
08:07  Orchestrator → DJ Brain: "Song 3, Break: Wetter + Song-Detail"
08:10  Orchestrator → DJ Brain: "Song 4, kein Break"
...
09:00  Hour Planner (LLM) ──→ hour_plan.json (für 09-10 Uhr)
```

---

## Was bei Kurt passieren müsste

Die entscheidende Frage: "Was müsste bei mir passieren, damit ich mir das regelmäßig anhören würde?"

### Vertrauen
- Der DJ darf nicht nerven. Das heißt: weniger Breaks, kürzere Texte, keine Wiederholungen.
- Die Song-Auswahl muss überraschend sein, aber nicht fremd. "Oh, nett" statt "was soll das?"

### Vorhersehbarkeit
- Montag morgen ≠ Freitag abend. Die Unterschiede müssen spürbar sein, aber nicht willkürlich.
- Wenn Kurt um 19:30 zur ZiB schaltet, sollte die Musik davor und danach unterschiedlich sein.

### Qualität
- Die DJ-Texte müssen sich natürlich anhören, nicht wie ein LLM-Prompt klingen.
- Die Song-Übergänge müssen musikalisch Sinn ergeben (Tempo, Tonart, Energie).

### Minimaler Aufwand
- Kurt sollte nicht täglich eingreifen müssen.
- Das System sollte sich selbst überwachen (z.B. "heute haben sich 3 Songs wiederholt — Problem?").

---

## Drei Ebenen der Einflussnahme (Sidestepper → Radio)

Die Main-Session ("ich") kann das Radioprogramm beeinflussen, ohne den Stream direkt zu steuern. Die Architektur entkoppelt Entscheidung (Main-Session) von Ausführung (System).

### Ebene 1: Main-Session (nicht zeitkritisch)
Während eines Gesprächs kann ich Intentionen in Dateien schreiben:

| Aktion | Datei | Wirkung |
|--------|-------|---------|
| Genre/Emphasis ändern | `day-context.json` | Day Planner berücksichtigt es beim nächsten Lauf |
| Songs priorisieren | `song-priorities.json` | Flow Agent bevorzugt diese Songs |
| Stimmung setzen | `day-context.json` | Mood-Override für die nächsten Stunden |
| DJ Break anfordern | `dj-break-requests.json` | Wird beim nächsten Heartbeat verarbeitet |

Beispiel: Kurt sagt "heute eher ruhig" → ich schreibe `{"mood": "ruhig", "energy": 3}` in day-context.json → Day Planner passt die Mood-Kurve an.

### Ebene 2: Heartbeat (zeitkritisch, aber nicht sofort)
Der Heartbeat (alle ~30 Min.) kann:
- Ausstehende DJ-Break-Requests verarbeiten
- Stimmungskontext aus der laufenden Session ableiten
- Playlist-Frische prüfen

### Ebene 3: Cron-Job (Planungsebene)
- Day Planner (täglich 6:00)
- Hour Planner + Flow Agent (stündlich)

### Datei-Schnittstelle
```
Main-Session schreibt →          System liest
─────────────────────            ──────────────
day-context.json          →     Day Planner
song-priorities.json      →     Flow Agent
dj-break-requests.json    →     Heartbeat → Orchestrator
```

Die Main-Session muss nie direkt auf den Stream zugreifen. Sie schreibt Intentionen, das System setzt sie um.

### Stimmungskontext (Mood Context)
Der Heartbeat leitet den Stimmungskontext aus der laufenden Session ab:
- Was wurde besprochen? (Thema, Tonfall, Tempo)
- Tageszeit und Wochentag
- Explizite Signale ("heute eher ruhig")

Format in `day-context.json`:
```json
{
  "energy": 5,
  "mood": "nachdenklich",
  "detected_at": "2026-05-08T17:54:00",
  "source": "conversation",
  "notes": "Kurt denkt über Architektur nach, ruhiges Tempo"
}
```

**Prototype:** Der Heartbeat aktualisiert diese Datei bei jedem Durchlauf. Noch kein Konsument — das ist nur ein Test, um zu sehen, ob die Erkennung funktioniert.

---

## Realistischer Implementierungsweg

### Phase 1: Song-Datenbank (Fundament)
- Schema definieren
- Bestehende Library (11.727 Pools + 20.626 gesamt) klassifizieren
- LLM-Batch-Klassifizierung (10-20 Songs pro Call, wie Kurt vorgeschlagen hat)
- Algorithmus implementieren

### Phase 2: Flow Agent (Song-Auswahl ohne LLM)
- Song-Datenbank-Abfrage implementieren
- Ersetzt die aktuelle "DJ Brain wählt Song"-Logik
- Suggestion Pools bleiben als Override/Präferenz

### Phase 3: Hour Planner (DJ-Break-Struktur)
- LLM plant den Stundenablauf
- DJ-Breaks werden vorab geplant, nicht ad hoc
- Verschiedene Inhalte pro Break (nicht immer alles)

### Phase 4: Day Planner (Kontextbewusstsein)
- Wetter-Integration
- Hörer-Erkennung (wenn möglich)
- Mood-Kurve über den Tag

### Phase 5: DJ Brain-Optimierung
- Besserer Input → besserer Text
- Längere Kontextfenster für den DJ Brain
- Möglichkeit, auf Hörer-Feedback zu reagieren

---

## Offene Fragen

1. **Soll der DJ Brain auch den Song wählen dürfen?** Oder bekommt er den Song vom Flow Agent zugewiesen und schreibt nur noch den Text?
2. **Wie geht das System mit Requests um?** Wenn ein Hörer einen Song requestet, der nicht in der Datenbank ist — ignorieren, kaufen, oder Fallback?
3. ~~Wie wird "Stimmung" gemessen?~~ → Teilweise beantwortet: Heartbeat leitet Stimmung aus laufender Session ab (siehe "Drei Ebenen der Einflussnahme"). Offen: ob und wie das der Day Planner nutzt.
4. **Wie oft soll der DJ sprechen?** Die aktuelle Regel (nach jedem Song) ist zu oft. 3er-Blöcke wären besser, aber wie flexibel?
5. **Soll das System lernen?** Wenn Hörer Songs bewerten (thumbs up/down), soll das die Song-Auswahl beeinflussen?
6. **Wie wird die Show-Rotation beeinflusst?** Soll der Day Planner die Show-Reihenfolge ändern können, oder ist sie fix?
