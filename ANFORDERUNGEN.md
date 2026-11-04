# Anforderungen: wifionice

## Zweck

`wifionice` bedient das WIFIonICE-Captive-Portal im Zug (`wifi.bahn.de` /
`login.wifionice.de`). Menschen sollen ohne Zugangsdaten den Portalstatus
prüfen, die Zuggeschwindigkeit lesen, einen Checkin inklusive AGB verbindlich
durchführen und sich wieder abmelden können. Das Werkzeug ist kein offizielles
Produkt der Deutschen Bahn.

## Nachfrage

| Quelle | Datum | Beleg |
|---|---|---|
| Tool-Brief der CLI-Routine (`scratch/BRIEF.md`) | 2026-11-04 | Bisheriges Tool deckt Checkin, Status, Speed und Logout ab; die Lücken sind konkret benannt (AGB-Rückfrage, `--confirm`, JSON bei Pipe, Doku). |
| `README.md`, Abschnitt „Live-Check“ | 2026-10-21 | Nutzungsszenarien und beobachtetes Portalverhalten (nur im Zug vollständig erreichbar). |
| `docs/UX.md` | 2026-11-04 | Drei wichtigste Nutzeraufgaben als abtippbare Sitzungen festgehalten. |
| GitHub-Repo `smlfg/wifionice-cli` | laufend | Bestehendes öffentliches CLI-Repo mit Contract-Tests und Fake-Server; Nachrüstung statt Neubau. |

Eine zusätzliche externe Marktrecherche (Smithery/Glama/Reddit) war für diese
Nachrüstung nicht nötig; der Bedarf ergibt sich aus dem bestehenden Tool und den
dokumentierten Nutzungsszenarien. Die Quellen und das Datum werden bei einer
späteren Demand-Prüfung ergänzt.

## Funktionale Anforderungen

### F1 – Portalstatus (`status`)

- Liest `GET {base}/cna/wifi/user_info`.
- Bei HTTP 404 fällt der Status lesend auf `GET {base}/de/` zurück.
- Zeigt im Terminal Portal-URL, Erreichbarkeit und Session-Zustand, z. B.
  `Portal: …`, `Erreichbar: ja`, `Session: nicht angemeldet`.
- Exit-Code 0 bei erreichbarem Portal; Netzwerkfehler → 3, Parsefehler → 4.

### F2 – Zuggeschwindigkeit (`speed`)

- Liest `GET {iceportal}/api1/rs/status` und zeigt die Zuggeschwindigkeit in
  km/h, Servicelevel und Verbindungsstatus.
- Es ist keine Bandbreitenmessung; `--bandwidth` wird mit Exit-Code 1 abgelehnt.
- Leerer Body außerhalb des Zuges → Exit-Code 4 mit verständlicher Meldung,
  kein erfundener Wert.

### F3 – Checkin inklusive AGB (`checkin`)

- Zeigt zuerst Portal-URL und AGB-Hinweis.
- Fragt im TTY auf stderr `Checkin verbindlich? [j/N]` (Default Nein).
- `N`/Enter sendet keinen Request und schreibt keinen State (Exit-Code 0).
- `j` sendet alle Requests: primär `POST /cna/logon`; bei HTTP 404 den
  Legacy-Fallback mit `GET /de/` und `POST /de/` (`login=true`, `CSRFToken`).
- `--accept-terms` bleibt die explizite AGB-Zustimmung. `--confirm`/`--yes`
  sind nur für nicht-interaktive Agenten gedacht. Ohne TTY sendet die CLI nur
  mit `--accept-terms` und (`--confirm` oder `--yes`), sonst Abbruch vor jedem
  Request mit Exit-Code 1.
- Erfolg schreibt den lokalen Session-State ohne Secrets.
- `--dry-run` zeigt den geplanten Ablauf, sendet nichts und schreibt nichts.

### F4 – Logout (`logout`)

- Idempotent und ohne Rückfrage.
- Versucht best effort `POST /cna/logoff`; Fehler sind Warnungen.
- Löscht den lokalen Session-State. Fehlt er, bleibt Exit-Code 0.
- `--dry-run` sendet nicht und löscht nichts.

### F5 – Konfiguration und Version

- `config` zeigt die aufgelöste Konfiguration inklusive Quellen.
- `version` zeigt die Paketversion. Beide brauchen kein Netzwerk.
- Basis-URL über `WIFIONICE_BASE_URL`, ICE-Portal über
  `WIFIONICE_ICEPORTAL_URL`; Präzedenz Umgebung > Datei > Default.

### F6 – Ausgabe und JSON

- Terminalausgabe ist lesbar und deutsch.
- JSON nur mit `--json` oder automatisch, wenn stdout kein TTY ist.
- Mit JSON steht genau ein Objekt auf stdout; Prompts/Warnungen gehen auf
  stderr. Fehler haben die Form
  `{"ok": false, "error": {"code": …, "message": …}}`.

## Nicht-funktionale Anforderungen

- Keine Zugangsdaten, keine Secrets in Repo, State, Logs oder Ausgaben.
- Keine Tracebacks bei erwarteten Fehlern, Strg+C oder EOF.
- Exit-Codes wie in `INTERFACE.md`; bestehende Codes 0, 1, 2, 3, 4 und 130
  bleiben erhalten.
- Alle Tests laufen offline gegen `tests/fake_server.py` bzw.
  `tests/harness/fake_server.py`; keine echten Portalzugriffe in Tests.
- Live-Prüfungen sind ausschließlich lesende GET-Requests auf öffentliche
  Seiten. Kein echter Checkin, keine AGB-Zustimmung, keine Schreibzugriffe.
- Python ≥ 3.11 gemäß `pyproject.toml`; Laufzeit nur Standardbibliothek plus
  `httpx`/`requests` (bestehende Abhängigkeiten).
- Lizenz MIT, Copyright smlfg.

## Akzeptanz

- Jede der drei UX-Sitzungen aus `docs/UX.md` hat mindestens einen Test unter
  `tests/acceptance/` gegen den Fake-Server.
- `python tests/harness/ux_check.py . --spec-only` endet mit Exit-Code 0.
- `README.md` beginnt mit einem Schnellstart, dessen Befehle wörtlich aus den
  UX-Sitzungen stammen.
- Die bestehenden Contract-Tests bleiben erhalten und werden bei geändertem
  Verhalten an diese Anforderungen angepasst, nicht gelöscht.

## Nicht im Scope

- Echte Anmeldung mit Zugangsdaten oder Speicherung von Konten.
- Bandbreitenmessung.
- Automatischer Re-Login oder Änderungen an der Portal-API.
- Push, Releases oder GitHub-Workflows.
