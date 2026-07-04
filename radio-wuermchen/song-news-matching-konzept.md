# Song-News-Matching: Konzept & Evaluierungsbeispiele

**Erstellt:** 2026-04-02
**Kontext:** Diskussion über Verbesserung des DJ Orchestrators bei Radio Würmchen — wie Songs thematisch zu Nachrichtenmeldungen gematcht werden können, statt nur per Stimmung oder Substring.

---

## Matching-Strategien (Taxonomie)

Aus der Analyse konkreter Beispiele ergeben sich diese Strategien, sortiert nach Komplexität:

### Strategie 1: Direktes Keyword im Titel
Schlüsselwörter aus der Schlagzeile direkt im Songtitel suchen.
- Einfachste Strategie, aktuell teilweise implementiert (Substring-Match im DJ Orchestrator)
- Probleme: "NYT" → "anything" (ungewollte Substring-Treffer), keine semantische Filterung

### Strategie 2: Entitäten-Match (Länder, Personen, Orte)
Genannte Entitäten in Meldung → passende Künstler-Herkunft, Songtitel, Textinhalte.
- "Ungarn" → "Hungaria"
- "Amerikaner" → Songs mit "American"
- "Megan Thee Stallion" → etwas von der Rapperin selbst spielen

### Strategie 3: Themen-Cluster
Meldung einem Themenfeld zuordnen → Songs aus diesem Cluster.
- Schule/Bildung → "Another Brick in the Wall", "School" (Supertramp)
- Weltraum/Mond/Rakete → Mond-, Raketen-, Weltraumsongs
- Fußball/WM → Fußballsongs, aber auch Fußballhymnen im weiteren Sinne ("We are the champions", "Seven nation army")
- Ski/Sport → Schi-Songs, Sport-Songs
- Auto/Verkehr → "Autobahn", "Highway", Auto-Songs generell

### Strategie 4: Wortspiel / Wort-im-Wort / Kreative Ableitung
Wortbestandteile oder kreative Assoziationen.
- "Geburtsrecht" → "Birthday"
- "Amoklauf" → Songs über Laufen ("Run to you", "Keep on running") — aber niedrigere Konfidenz, da Kontext negativ
- "Apple ist 50" → Songs mit "Apple" (auch wenn nicht die Firma gemeint)
- ASFINAG/Lobau → "Autobahn", "Highway"
- "Offener Brief" → Songs mit "Message", "Letter"

### Strategie 5: Konnotations-bewusstes Keyword-Matching
Nicht nur ob ein Keyword vorkommt, sondern ob die *Bedeutungsnuance* passt.
- "Brandgefahr: Stellantis ruft 700.000 Autos zurück" → Brand-Songs mit unkontrolliertem Feuer bevorzugen
  - ✅ "Hurra, Hurra, die Schule brennt" (unkontrollierter Brand)
  - ✅ "Radio brennt" (unkontrollierter Brand)
  - ⚠️ "Beds are burning" (eher metaphorisch/politisch)
  - ❌ "Keep the fire burning" (positiv-metaphorisch)

### Strategie 6: Künstler-Kontext / Popkultur-Wissen
Wissen über den Künstler jenseits seiner Musik.
- Patrick Duffy = Bobby Ewing aus "Dallas" (Öl-Dynastie) → Meldung über Öltanker/Straße von Hormus
- Mireille Mathieu = Französin → Meldung mit Frankreich als Akteur

### Strategie 7: Szenerie/Narrativ-Match ("Bilder im Kopf")
Das *innere Bild* oder die *Szene*, die ein Lied beschreibt, matcht mit der Nachrichtensituation.
- "Major Tom" (Peter Schilling), "Space Oddity" (Bowie), "Rocket Man" (Elton John) → alle beschreiben einen einsamen, schiefgehenden Weltraumflug → passen alle auf Weltraummissionen
- Vom Titel her nicht immer erkennbar — erfordert Wissen über den Songtext/die Songhandlung
- **Kurts Beschreibung:** "Beim Hören von Liedern bilden sich gewisse Bilder im Kopf, die eine bestimmte Situation beschreiben. Wenn in den Nachrichten eine ähnliche Situation beschrieben wird, gibt es ein Matching."

### Strategie 9: Entstehungsgeschichte / Song-Hintergrund
Die *Geschichte hinter dem Song* matcht, auch wenn weder Titel noch Text es verraten.
- "I don't like Mondays" (Boomtown Rats) basiert auf einem Schul-Amoklauf (Brenda Spencer, San Diego, 1979) — aber der Text ist allegorisch, die Verbindung ist ohne Hintergrundwissen nicht erkennbar
- Schwierigste Strategie: erfordert eine Song-Kontext-Datenbank (nicht nur Lyrics, sondern "wovon handelt der Song wirklich?")
- LLM-gestützt für Top-Rotation (2.000–3.000 Titel) machbar — bekannte Songs haben gut dokumentierte Hintergrundgeschichten

### Strategie 10: Stimmungs-Match (aktuell implementiert)
DJ Brain matcht Musik zur Stimmung der Nachricht. Funktioniert als Fallback, aber produziert generische Ergebnisse.

---

## Evaluierungsbeispiele

### Beispiel 1: "Frankreich und Indien kooperieren, um Straße von Hormus freizubekommen"
| Song | Strategie | Qualität |
|------|-----------|----------|
| "Together we're strong" (Mireille Mathieu & Patrick Duffy) | Thema (Kooperation) + Entität (Mathieu=Frankreich) + Popkultur (Duffy=Dallas=Öl) | ⭐⭐⭐ Dreifach-Match |

### Beispiel 2: "Monika Maron: Zeugnisse eines streitbaren Freigeists"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Titel mit "Geist" oder "Ghost" | Keyword (Wort-im-Wort: "Freigeist") | ⭐⭐ Solide |

### Beispiel 3: "Will Geburtsrecht ändern: Trump bei Anhörung in Höchstgericht"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Titel mit "Birthday" | Wortspiel ("Geburtsrecht" → Geburt → Birthday) | ⭐⭐ Kreativ |
| "Streets of Minneapolis" (Bruce Springsteen) | Songtext-Wissen (Trump wird im Text erwähnt) | ⭐⭐⭐ Nicht offensichtlich, starker Match |

### Beispiel 4: "Lehrplanreform: Stundentafeln können auch gleich bleiben"
| Song | Strategie | Qualität |
|------|-----------|----------|
| "Another Brick in the Wall" (Pink Floyd) | Themen-Cluster (Schule) | ⭐⭐⭐ Ikonisch |
| "School" (Supertramp) | Themen-Cluster (Schule) | ⭐⭐ Direkt |

### Beispiel 5: "Wer sein WM-Ticket hat, wer zittern muss"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Fußballsongs | Themen-Cluster (Fußball) | ⭐⭐ Offensichtlich |
| "We are the champions" (Queen) | Themen-Cluster (Fußball-Hymne im weiteren Sinn) | ⭐⭐⭐ Universelle Assoziation |
| "Seven nation army" (White Stripes) | Themen-Cluster (Fußball-Hymne im weiteren Sinn) | ⭐⭐⭐ Stadion-Klassiker |

### Beispiel 6: "Pez und Keli: 'Made in Linz'-Nostalgie im Stadtmuseum"
| Song | Strategie | Qualität |
|------|-----------|----------|
| "Future Nostalgia" (Dua Lipa) | Keyword + Stimmung ("Nostalgie") | ⭐⭐ Passend |

### Beispiel 7: "Rakete von Mondmission Artemis 2 gestartet"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Mond-, Raketen-, Weltraumsongs | Themen-Cluster (Weltraum) | ⭐⭐ Standard |
| "Major Tom" / "Space Oddity" / "Rocket Man" | Szenerie-Match (einsamer Weltraumflug) | ⭐⭐⭐ Narrativ passt |

### Beispiel 8: "Iranischer Präsident schickt Botschaft an Amerikaner"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Titel mit "Message" oder "Letter" | Keyword ("Botschaft" = Message) | ⭐⭐ Solide |
| Titel mit "American" oder "President" | Entitäten-Match | ⭐⭐ Direkt |

### Beispiel 9: "Tausende in Teheran bei Begräbnis von Marinekommandeur"
| Song | Strategie | Qualität |
|------|-----------|----------|
| "Yellow Submarine" (Beatles) | Themen-Cluster (Marine → U-Boot) | ⭐⭐ Augenzwinkernd |

### Beispiel 10: "Brandgefahr: Stellantis ruft 700.000 Autos zurück"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Auto-Songs | Themen-Cluster (Auto) | ⭐ Offensichtlich |
| "Hurra, Hurra, die Schule brennt" | Konnotations-Match (unkontrolliertes Feuer) | ⭐⭐⭐ Passt tonal |
| "Radio brennt" | Konnotations-Match (unkontrolliertes Feuer) | ⭐⭐ Passt |
| "Keep the fire burning" | ❌ Falsche Konnotation (positiv-metaphorisch) | — |

### Beispiel 11: "Musks SpaceX bereitet Börsengang der Rekorde vor"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Weltraumsongs | Themen-Cluster (SpaceX → Weltraum) | ⭐⭐ Standard |

### Beispiel 12: "Aus Italiens WM-Drama wird bittere Gewohnheit" / "Österreichs WM-Euphorie und die Qual der Wahl"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Fußballsongs + Fußballhymnen | Themen-Cluster (WM/Fußball) | ⭐⭐ Standard |

### Beispiel 13: "Skibergsteigen: ÖSV-Duo zeigt im Finale auf"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Schi-Songs, Sport-Songs | Themen-Cluster (Wintersport) | ⭐⭐ Standard |

### Beispiel 14: "Die große Sehnsucht nach dem iPod: Apple ist 50"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Songs mit "Apple" | Keyword/Wortspiel (Firma ≠ Frucht, aber Assoziation funktioniert) | ⭐⭐ Augenzwinkernd |

### Beispiel 15: "Papst traf Familie eines Opfers des Grazer Amoklaufs"
| Song | Strategie | Qualität |
|------|-----------|----------|
| "Run to you", "Keep on running" | Wortspiel (Amoklauf → Laufen) | ⭐ Niedrige Konfidenz — Kontext ist tragisch, Wortspiel evtl. unpassend |
| "I don't like Mondays" (Boomtown Rats) | Entstehungsgeschichte (Song basiert auf Schul-Amoklauf, aber Text ist allegorisch — Verbindung nur mit Hintergrundwissen erkennbar) | ⭐⭐ Thematisch passend, aber weit hergeholt für automatisches Matching |

### Beispiel 16: "Juden begehen weltweit Pessachfest"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Jiddische oder hebräische Musik | Kultureller Match | ⭐⭐ Respektvoll passend |

### Beispiel 17: "Megan Thee Stallion beruhigt Fans nach Schwächeanfall"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Etwas von Megan Thee Stallion | Entitäten-Match (Meldung über Künstlerin → ihre Musik) | ⭐⭐⭐ Offensichtlich und stimmig |

### Beispiel 18: "USA heben Sanktionen gegen Rodriguez auf"
| Song | Strategie | Qualität |
|------|-----------|----------|
| Etwas von einem Interpreten namens Rodriguez | Entitäten-Match (Name) | ⭐⭐ Direkt |
| Olivia Rodrigo | Namensähnlichkeit (Rodriguez ≈ Rodrigo) | ⭐⭐ Kreativ-augenzwinkernd |

---

## Rotations-Metriken (separates Thema)

### Ziel-Parameter
- **Bibliothek:** ~28.000–30.000 Titel
- **Verschiedene Titel in Rotation:** 7.000–10.000
- **Top-Titel Wiederholung:** ca. alle 1.000 Titel (~3 Tage)
- **Kopflastig, aber nicht zu stark:** Häufigkeitsverteilung soll nicht zu steil sein

### Referenzwerte
- **88.6 (Slogan):** "8.860 Titel im Musiksommer" — gemeint waren Gesamtplays inkl. Wiederholungen, nicht verschiedene Titel
- **88.6 (Realität):** ~900 verschiedene Titel im Standardprogramm (analysiert vor der Rock-Umstellung)
- **Radio Salzburg (Sommer 2016):** ~11.000 verschiedene Titel — Beweis, dass hohe Diversität im realen Betrieb machbar ist

### Messbare Metriken
- **Unique-Titel-Count** über Zeitfenster (Tag/Woche/Monat)
- **Wiederholungsabstand** pro Titel (Minimum, Durchschnitt, Median)
- **Gini-Koeffizient** der Häufigkeitsverteilung (0 = alle gleich oft, 1 = ein Titel dominiert)
- **Kopflastigkeit:** Anteil der Top-100/500/1000 Titel an Gesamtplays

### Datenquelle für Bewertungen
- Radio-Würmchen-Datenbank enthält Person "88.6-Hörer" mit Wunsch-, Hör- und Bewertungsdaten für >9.000 Titel
- Wertungen basieren auf 88.6 Best-Of-Sendungen und Countdowns
- **Einschränkung:** 88.6 war schon damals rock-orientiert; Wertungen spiegeln Rock-Bias wider, nicht ideale Radio-Würmchen-Rotation
- **Beobachtung:** Die wöchentlichen Best-Of-Sendungen haben wahrscheinlich die Entwicklung zum Rocksender *beschleunigt* — Rock-Titel standen regelmäßig an der Spitze und flossen dann verstärkt ins reguläre Programm ein (positive Feedback-Schleife)

---

## Historische Datenquellen & Entwicklung des Tagging-Systems

### kategorisierung.xls (2001–2006, ~4.409 Titel, 21 Spalten)
Manuell gepflegte Excel-Datei im Workspace. Kurt hat über Jahre bei jedem Hören eines bekannten Titels im Radio eine Zeile ergänzt oder erweitert. Datei zuletzt gespeichert: 06.05.2006.

**Gut befüllte Felder (>50%):**
- Rhythmus (99%), "gehört auf" = Sender-Airplay-Geschichte (98%), Tempo/BPM (54%)

**Teilweise befüllt (20–45%):**
- Stil/Genre, Härtegrad (Zahlenwert), Freundlichkeitsgrad (Zahlenwert), Tonart, Jahr

**Selten, aber wertvoll (<10%):**
- "Ungreifbare Stimmung" (5.7%, 179 einzigartige Beschreibungen) — z.B. "schüchtern, wohlig", "kalt, Nacht, heimelig", "Tanz, Strand, Party, ausgelassen" → das sind die "Bilder im Kopf" aus Strategie 7
- "Thema" (4.0%, 131 einzigartige Themen) — z.B. "Morgenhektik", "Ich bin bei dir", "Disco, Tanz, Befreiung" → Vorläufer des Song-News-Matching-Konzepts

**Rotationsmodell (Tabelle3):**
11 Stufen von "Top" (240er Rotation, 20 Titel) bis "Moderne Schmankerln" (9.000er Rotation, 750 Titel). Basierte auf einer Bibliothek von ~2.000 Titeln (daher niedrigere Zahlen als die heutigen Zielwerte von 7.000–10.000 in einer 28.000er Bibliothek). Kurt hatte 2006 noch keine so genaue Vorstellung der idealen Rotation, zählte aber schon damals Rotationen realer Sender.

**Warum aufgegeben:** Zu chaotisch — die selten befüllten Felder hatten kein klares Verwendungskonzept, und die Konsistenz fehlte.

### Radio-Würmchen-Datenbank (aktuelles System)
Nachfolger der Excel-Kategorisierung mit einem grundlegend anderen Ansatz:
- **Ein konsistentes Tag-Feld** statt vieler inkonsistenter Spalten
- **Systematisch beim Einspielen befüllt** → existiert für fast alle Titel, die als MP3 vorhanden sind
- **Fokus auf Klang** (wie klingt die Musik?), nicht auf Thema/Lyrics
- "Ungreifbare Stimmung" vereinzelt noch vorhanden, "Thema" nur wenn es sich auch musikalisch so anfühlt

**Vorteil gegenüber automatischen Methoden:**
- Schlägt `pool_refill.py` (LLM-basiert) und `generate_pools` (Interpreten-basiert) bei unbekannteren Titeln
- Grund: Beide automatischen Methoden haben keine Informationen über den tatsächlichen Klang oder die musikalische Konsistenz unbekannterer Titel — das LLM kennt sie nicht, und der Interpreten-Ansatz ignoriert, dass ein Künstler verschiedenste Stile haben kann
- Das manuelle Tagging basiert auf tatsächlichem Hören beim Einspielen → erfasst, was automatisch nicht verfügbar ist

### Iterativer Pool-Optimierungs-Loop (vor Projektpause)
Kurz vor der Projektpause entwickelte Kurt einen manuellen Optimierungs-Loop für die Suggestion Pools:

**Der Prozess:**
1. DJ Brain wählt Titel aus dem bestehenden Pool für eine Sendung
2. `dj_report.py` analysiert, welche Titel gewählt/nicht gewählt wurden, und schätzt daraus Wertungen
3. Kurt gibt diese Wertungen in das Radio-Würmchen-Programm ein
4. Der dortige Algorithmus (ursprünglich für menschliche Hörer entwickelt — "lernt" Musikgeschmack durch Tag-Analyse, Interpreten-Präferenzen, Ähnlichkeitsnetzwerk) extrapoliert Schätzwertungen für den gesamten MP3-Pool
5. Aus den Top-Titeln wird ein neuer Suggestion Pool gebildet
6. Zurück zu Schritt 1

**Ergebnis:** Nach 2–3 Iterationen konvergierte der Prozess für die Morgenshow — der DJ Brain wählte Titel fast exakt in der Pool-Reihenfolge, kaum ein als "gut" geschätzter Titel blieb ungewählt.

**Bedeutung:**
- Beweist, dass der Tag-basierte Algorithmus die *impliziten Präferenzen* des DJ Brains pro Sendung modellieren kann
- Der Algorithmus "versteht", was das LLM aufgrund seines Show-Promptings bevorzugt, besser als das LLM es selbst artikulieren könnte
- Nutzt Komponenten mit lernbarer Gewichtung: Tag-Korrelationen (welche Tags → gute/schlechte Wertung), Interpreten-Präferenzen, Ähnlichkeitsnetzwerk — Gewichtung wird pro "Person" (= pro Sendung) individuell gelernt

**Parallele zu Meta-Harness:**
Dieser manuelle Loop ist strukturell identisch zum Meta-Harness-Prinzip:
- DJ Brain Auswahl = **Evaluation**
- dj_report Wertungen = **Traces/Feedback**
- Kurt als manueller Eingeber = **Proposer**
- Radio-Würmchen-Algorithmus = **Harness-Generator**
- Neuer Pool = **Neuer Harness-Kandidat**
- 2–3 Iterationen bis Konvergenz = Meta-Harness braucht typisch 5–15

Der Unterschied: Kurt war der manuelle Proposer. Eine Automatisierung dieses Loops (dj_report → Wertungen automatisch einspeisen → Pool automatisch regenerieren) wäre ein minimaler Meta-Harness ohne LLM-Proposer — rein algorithmisch, fast kostenlos.

**Implikation für Matching-Engine:**
Für Song-News-Matching (Strategien 1–9) reicht das Klang-Tagging allein nicht — dafür bräuchte man zusätzlich Themen-/Lyrics-/Kontext-Daten. Aber für die Grundfunktion "welcher Song passt klanglich in welche Sendung" ist das bestehende System dem LLM überlegen. Ein hybrides System (manuelles Klang-Tag + LLM für Themen/Lyrics/Kontext) könnte beide Stärken kombinieren.

## Nächste Schritte (offen)

1. **Evaluierungsset erweitern:** Weitere Matching-Beispiele sammeln
2. **Themen-Tagging:** Songs systematisch mit Themen-Tags versehen (manuell oder LLM-gestützt)
3. **Matching-Engine entwerfen:** Mehrstufig — von Keyword bis Szenerie-Match
4. **Meta-Harness-Experiment:** Verschiedene Matching-Strategien automatisch gegen Evaluierungsset testen
5. **Rotations-Analyse:** Aktuelle Playlogs auswerten (Unique-Count, Wiederholungsabstände)

---

## Bezug zu Meta-Harness (Paper, 2026-04-02)

Dieses Konzept ist ein idealer Kandidat für Meta-Harness-Prinzipien:
- **Klar messbar:** Song-News-Match hat ein Bewertungsset (diese Beispiele), Rotation hat quantitative Metriken
- **Harness-Problem:** Das *Wie* der Kontextaufbereitung (welche Strategien, in welcher Reihenfolge, mit welcher Gewichtung) ist genau das, was Meta-Harness optimiert
- **Machbar:** Pool Refill + Song-Matching auf einem Windows-PC mit OpenClaw testbar
- **Siehe auch:** `meta-harness-analyse.md` im Workspace
