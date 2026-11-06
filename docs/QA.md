# Pflicht-QA: wifionice

- **Datum:** 2026-11-06
- **Version/Commit:** `wifionice 0.1.0` (Git-Commit `ae6ac59`, Branch `master`, Arbeitsbaum sauber)
- **Prüfer-Setup:** frische `pipx`-Installation wie im README-Schnellstart, Protokoll `scratch/qa/pipx-install.log`
  (`installed package wifionice 0.1.0`, App `wifionice`). Alle Aufrufe ausschließlich über
  `PATH=$PWD/scratch/pipx/bin:$PATH`.
- **Offline:** Fake-Server aus `tests/harness/` (ux-routes aus `docs/UX.md`) über `WIFIONICE_BASE_URL`; Request-Protokoll in `scratch/qa/requests.log`.
- **Live:** ausschließlich lesende GET-Requests (`https://iceportal.de/api1/rs/status`, `https://wifi.bahn.de/cna/wifi/user_info`). Kein echter Checkin, keine AGB-Zustimmung, keine Anmeldung.

## Ergebnis

| Prüfung | Befehl | Erwartet | Ergebnis | Beleg (gekürzt) |
|---|---|---|---|---|
| Pipx-Installation | `pipx install git+https://github.com/smlfg/wifionice-cli` | App `wifionice` installiert | OK | `scratch/qa/pipx-install.log`: „installed package wifionice 0.1.0“ |
| Pflicht-QA-TT | `wifionice --version` | Exit 0, Versionsnummer | OK | exit 0, `0.1.0` |
| README-Schnellstart: status im Pseudo-TTY | `script -qc "… wifionice status"` | lesbare Terminal-Ausgabe, Exit 0 | OK | `scratch/qa/01-status-tty.log`: „Portal: …“, „Erreichbar: ja“, „Session: nicht angemeldet“ |
| README-Schnellstart: speed im Pseudo-TTY | `wifionice speed` (tty) | Zuggeschwindigkeit in km/h | OK | `scratch/qa/02-speed-tty.log`: „Zuggeschwindigkeit: 109 km/h“ (faktengetreu aus Fixture `iceportal_status.json`) |
| README-Schnellstart: checkin mit „N“ | `wifionice checkin` (tty), Antwort `N` | Zusammenfassung + AGB-Hinweis, Prompt, **kein** Request | OK | `scratch/qa/03-checkin-N.log`: „Checkin abgebrochen; keine Anfrage gesendet."; `scratch/qa/requests.log`: kein POST |
| README-Schnellstart: checkin mit „j“ | `wifionice checkin` (tty), Antwort `j` | sendet `POST /cna/logon`, Erfolgsmeldung | OK | `scratch/qa/04-checkin-j.log`: „Checkin erfolgreich (Methode: cna)."; `requests.log`: `POST /cna/logon` |
| Checkin: EOF im TTY | `checkin` (tty, EOF) | Abbruch ohne Request, kein Traceback | OK | `scratch/qa/05-checkin-eof.log`: kein Traceback, kein Request, COMMAND_EXIT_CODE 130 |
| status an Fake | `wifionice status` (notty) | JSON automatisch bei nicht-TTY stdout | OK | `scratch/qa/06-notty.txt`: JSON-Objekt, `authenticated: false`, `method: cna` |
| speed an Fake | `wifionice speed` (notty) | JSON automatisch | OK | `scratch/qa/06-notty.txt`: `train_speed_kmh: 109.0`, `measurement: train_speed_kmh` |
| checkin nicht-TTY, nur `--accept-terms` | `checkin --accept-terms` (notty) | Abbruch vor jedem Request mit Hinweis | OK | `scratch/qa/07-checkin-notty.err`: „missing --confirm or --yes; next step: …", Exit 1, kein Request |
| checkin nicht-TTY ohne Flags | `checkin` (notty) | Abbruch vor jedem Request mit Hinweis | OK | `scratch/qa/06-notty.txt`: „missing --accept-terms and --confirm or --yes …", Exit 1, kein Request |
| checkin Agenten-Modus | `checkin --accept-terms --confirm --json` (notty) | sendet alle Formularschritte | OK | `scratch/qa/09-13.txt`: `{checked_in: true, method: cna}`, Exit 0; `requests.log`: `POST /cna/logon` |
| checkin `--dry-run` | `checkin --accept-terms --dry-run --json` | plant Requests, sendet nichts, schreibt nichts | OK | `scratch/qa/09-13.txt`: Plan mit `POST /cna/logon` + Legacy-Fallback; `requests.log`: kein Request |
| status/speed lehnen `--dry-run` ab | `status --dry-run` / `speed --dry-run` | verständliche Absage mit next step | OK | `scratch/qa/14-18.txt`: „status does not support --dry-run; next step: …", Exit 1 |
| `--bandwidth` abgelehnt | `speed --bandwidth` | Meldung, kein erfundener Wert | OK | `scratch/qa/14-18.txt`: „… not a bandwidth test …", Exit 1 |
| logout idempotent | `wifionice logout --json` | best effort Portal-Logoff, State gelöscht, Exit 0 | OK | `scratch/qa/09-13.txt`: `removed: true, portal_logoff: false, detail: "local state deleted …"`; `requests.log`: `POST /cna/logoff` |
| logout ohne State | `logout --dry-run` (nichts gespeichert) | „no local session state found", Exit 0 | OK | `scratch/qa/09-13.txt` |
| `config` | `wifionice config --json` | aufgelöste Werte inkl. Quellen | OK | `scratch/qa/09-13.txt`: `base_url` aus `env`, `sources` vollständig |
| version | `wifionice version` | Paketversion | OK | `0.1.0` |
| `--help` (Hauptbefehl) | `wifionice --help` (tty) | verständlich, Exit 0 | OK | `scratch/qa/14-help.log`: alle Befehle mit Kurztext |
| `checkin --help` | `wifionice checkin --help` (tty) | dokumentiert `--accept-terms`, `--confirm/--yes`, `--dry-run` | OK | `scratch/qa/15-checkin-help.log` |
| TTY → Text, nicht-TTY → JSON | `status` tty vs. notty | Text im Terminal, JSON bei Pipe | OK | `scratch/qa/01-status-tty.log` vs. `scratch/qa/06-notty.txt` |
| JSON valide | `status --json`, `speed --json`, Fehler-JSON | genau ein parsebares JSON-Objekt je Aufruf | OK | `scratch/qa/json-check.txt`: alle `json.loads` ok |
| Netzfehler (falsche Base-URL) | `WIFIONICE_BASE_URL=http://127.0.0.1:9 wifionice status --json` | Exit 3, Meldung mit next step, kein Traceback | OK | `scratch/qa/19-badbase.txt`: „cannot reach …; next step: check the network …", Exit 3 |
| Netzfehler (speed) | `wifionice speed` mit falscher Base-URL | Exit 3, Meldung mit next step | OK | `scratch/qa/19-badbase.txt`, kein Traceback |
| Ungültige Base-URL | `WIFIONICE_BASE_URL=nicht-eine-url wifionice status` | Exit 1, klare Validierungsmeldung, kein Traceback | OK | `scratch/qa/19-badbase.txt`: „base_url must be an absolute http or https URL …", Exit 1 |
| Live: speed (Hauptlesefall, lesend) | `wifionice speed --json` (echtes `iceportal.de`) | außerhalb des Zugs: Exit 4, keine erfundene km/h-Zahl | OK | `scratch/qa/20-21-live.txt`: „onboard ICE portal returned an empty body (train speed is only available on board)", Exit 4; konform mit README Live-Check |
| Live: status (lesend) | `wifionice status --json` (echtes `wifi.bahn.de`) | ohne Zug-WLAN: Exit 3, kein Traceback | OK | `scratch/qa/20-21-live.txt`: `SSL: UNEXPECTED_EOF`, Exit 3; konform mit README Live-Check |
| Test-Suite | `scratch/venv/bin/pytest -q` | grün | OK | **100 passed, 6 skipped** (Skips: optionale MCP-Tests, Env nicht gesetzt) |
| Traceback-frei | alle QA-Logs | keine Tracebacks, auch nicht bei EOF/Strg+C | OK | `grep -i traceback` über `scratch/qa/*` ohne Treffer |

**Zählung: 28 OK / 28 gesamt.**

## Semantische Prüfungen

- `speed` liefert exakt die Geschwindigkeit aus der Route (`Fixture speed: 109` → „Zuggeschwindigkeit: 109 km/h"; JSON `train_speed_kmh: 109.0`). Kein Wert wird erfunden.
- `status` meldet inhaltlich korrekt „nicht angemeldet" (`authenticated: "0"` in der Route) und die Methode `cna`; die zugehörigen Mengenwerte (`limit_mb`/`used_mb`) stimmen mit der Route überein — Angemeldet-Sein gilt nur, wenn die Route es meldet (Login-Erfolg braucht Beweis).
- Checkin-Gate: `N` und `--dry-run` und EOF veranlassen **null** Requests (Request-Protokoll `scratch/qa/requests.log`); `j` und `--accept-terms --confirm` senden `POST /cna/logon`.

## Offene FAILs

Keine. (Anmerkung, kein FAIL: `status`/`speed` `--dry-run` werden bewusst mit Exit 1 abgelehnt — per Brief dokumentiert.)

