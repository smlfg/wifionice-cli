# Schnittstelle: wifionice

Verbindlicher Vertrag für den Befehl `wifionice`. Grundlage sind `docs/UX.md`,
`README.md` und die bestehenden Exit-Codes in `src/wifionice_cli/exit_codes.py`.
Änderungen an Flags, Ausgabe oder Exit-Codes brauchen eine Anpassung von
`docs/UX.md`, `README.md` und den Tests.

## Aufruf

```text
wifionice [globale Flags] <befehl> [befehlsspezifische Flags]
```

Es gibt keinen Login-Befehl und keine Zugangsdaten. `credential_env` ist leer.
Alle Befehle funktionieren ohne IDs, Pflicht-Optionen oder Positionsargumente;
die drei Hauptaufgaben sind `status`, `speed` und `checkin`.

## Befehle

| Befehl | Syntax | Zweck | Netzwerk |
|---|---|---|---|
| `status` | `wifionice status` | Portal erreichbar? Session aktiv? Liest `GET /cna/wifi/user_info`; bei HTTP 404 lesend `GET /de/`. | ja, lesend |
| `speed` | `wifionice speed` | Zuggeschwindigkeit in km/h aus dem Onboard-ICE-Portal (`GET /api1/rs/status`). Keine Bandbreitenmessung. | ja, lesend |
| `checkin` | `wifionice checkin [--accept-terms] [--confirm\|--yes]` | Portal-Checkin inklusive AGB. Zeigt Zusammenfassung und fragt im TTY `Checkin verbindlich? [j/N]`. | ja, schreibend nach Bestätigung |
| `logout` | `wifionice logout` | Idempotenter Logout: best effort `POST /cna/logoff`, danach lokalen State löschen. Keine Rückfrage. | ja, best effort |
| `config` | `wifionice config` | Aufgelöste Konfiguration inklusive Quellen anzeigen. | nein |
| `version` | `wifionice version` | Paketversion ausgeben. | nein |

`status` und `speed` lehnen `--dry-run` mit Exit-Code 1 ab, weil sie nur lesen.
`logout` ist idempotent: fehlt der lokale State, endet der Befehl trotzdem mit
Exit-Code 0 und versucht den Portal-Logoff best effort.

## Globale Flags

| Flag | Wirkung |
|---|---|
| `--json` | Genau ein JSON-Objekt auf stdout, auch im Fehlerfall. Prompts gehen auf stderr. |
| `--dry-run` | Keine Netzwerk-Requests und keine Schreibzugriffe. Planausgabe auf stdout. Gilt für `checkin` und `logout`; bei `status`/`speed` Exit-Code 1. |
| `--config PATH` | Alternative Konfigurationsdatei statt `~/.config/wifionice/config.json`. |

Ausgabeformat:

- **Mensch (TTY):** lesbare deutsche Zeilen, z. B. `Portal: …`,
  `Erreichbar: ja`, `Session: nicht angemeldet`, `Zuggeschwindigkeit: 109 km/h`.
  Kein JSON im Terminal.
- **JSON:** automatisch, wenn stdout kein TTY ist, oder explizit mit `--json`.
  Erfolg: `{"ok": true, ...}`; Fehler:
  `{"ok": false, "error": {"code": <exit-code>, "message": "…"}}`.
  Es steht genau ein JSON-Objekt auf stdout.
- Prompts und Warnungen gehen auf stderr. Fehler nennen den nächsten Schritt und
  enthalten keine Tracebacks, auch nicht bei Strg+C oder EOF.

## checkin

Syntax:

```text
wifionice checkin [--accept-terms] [--confirm|--yes] [--dry-run] [--json]
```

Ablauf:

1. Zusammenfassung mit Portal-URL und AGB-Hinweis
   (`Der Checkin bestätigt die Nutzungsbedingungen des WIFIonICE-Portals.`).
2. Im TTY fragt die CLI auf stderr `Checkin verbindlich? [j/N]` (Default Nein).
   Die Rückfrage hat Vorrang; `--accept-terms`, `--confirm` und `--yes` ersetzen
   sie im TTY nicht.
   - `N` oder Enter: kein Request, kein State-Schreibzugriff, Exit-Code 0.
   - `j`: alle Requests des Checkins werden gesendet.
3. Ohne TTY sendet die CLI nur mit `--accept-terms` **und** (`--confirm` oder
   `--yes`). Fehlt eine der beiden Zustimmungen, bricht sie vor jedem Request
   mit Exit-Code 1 ab und nennt die fehlende Flag.
4. `--dry-run` zeigt nur den geplanten Ablauf (keine Requests, kein State) und
   endet mit Exit-Code 0.

Request-Reihenfolge:

1. `POST {base}/cna/logon` mit JSON `{}` und den CNA-Headern
   (`X-Csrf-Token: csrf`, `X-Requested-With: XMLHttpRequest`,
   `Referer: {base}/cna/`). Antwort `result: "success"` → Methode `cna`.
2. Nur bei HTTP 404 auf `/cna/logon`: Legacy-Fallback mit lesendem `GET {base}/de/`
   (CSRF-Cookie) und anschließendem `POST {base}/de/` mit
   `login=true&CSRFToken=<token>` → Methode `legacy`.

Erfolgsmeldung im TTY: `Checkin erfolgreich (Methode: cna).` bzw.
`Checkin erfolgreich (Methode: legacy).` Danach wird der lokale State
geschrieben. Eine Portal-Ablehnung ist Exit-Code 2, ein Transportfehler
Exit-Code 3.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | Erfolg; auch ein vom Menschen mit `N` abgebrochener Checkin und ein idempotenter `logout` ohne lokalen State. |
| 1 | Ungültige Eingabe: Flags, fehlende Bestätigung/AGB-Zustimmung ohne TTY, `--dry-run` bei `status`/`speed`, Validierungsfehler. Auch argparse-Fehler. |
| 2 | Portal lehnt Checkin ab (Auth/AGB) bzw. HTTP 401/403. |
| 3 | Netzwerk-/Transportfehler (DNS, Timeout, HTTP 5xx). |
| 4 | Antwort oder Datei nicht parsebar (JSON, Config, State); auch leerer Body von `/api1/rs/status` außerhalb des Zuges. |
| 130 | Abbruch durch Strg+C oder EOF an einem Prompt. |

## Umgebungsvariablen

| Variable | Default | Zweck |
|---|---|---|
| `WIFIONICE_BASE_URL` | `https://wifi.bahn.de` | Basis-URL des Captive Portals (`ux-meta.base_url_env`, für Fake-Server). Absolut, Schema `http`/`https`. |
| `WIFIONICE_ICEPORTAL_URL` | `https://iceportal.de` | Onboard-ICE-Portal für `speed`. |
| `WIFIONICE_STATE` | `~/.local/state/wifionice/session.json` | Pfad des lokalen Session-States. |
| `WIFIONICE_TIMEOUT` | `5` | HTTP-Timeout in Sekunden. |
| `WIFIONICE_RETRIES` | `2` | HTTP-Versuche bei Transportfehler oder HTTP 5xx (mindestens 1). |
| `WIFIONICE_CONFIG` | `~/.config/wifionice/config.json` | Pfad der Konfigurationsdatei. |

Präzedenz: Umgebungsvariablen > Konfigurationsdatei > Defaults. Es gibt keine
Credential-Variablen und keine Secrets.

## Session-Pfad

Der lokale Session-State liegt standardmäßig unter
`~/.local/state/wifionice/session.json` (überschreibbar mit `WIFIONICE_STATE`).
Er enthält keine Secrets: Basis-URL, Methode, Zeitpunkt und den
Authentifizierungsstatus. `checkin` schreibt atomar, `--dry-run` schreibt nie,
`logout` entfernt die Datei.
