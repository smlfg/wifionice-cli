# wifionice

CLI für das WIFIonICE-Zug-WLAN (Captive Portal `wifi.bahn.de` / `login.wifionice.de`): automatischer Portal-Checkin inklusive AGB-Bestätigung, Session-Status, Zuggeschwindigkeit und lokaler Logout.

Kein offizielles Werkzeug der Deutschen Bahn. Nutzung auf eigene Verantwortung; für die Portalnutzung gelten die AGB der DB. Es werden keine Zugangsdaten benötigt und keine gespeichert.

## Installation

```bash
uv sync --extra dev
uv run wifionice --help
```

Alternativ: `pip install -e ".[dev]"`.

## Kommandos

Globale Flags: `--json` (genau ein JSON-Objekt auf stdout, auch im Fehlerfall), `--dry-run` (keine Netzwerk-Requests, keine Schreibzugriffe).

| Kommando | Zweck |
|----------|-------|
| `wifionice checkin --accept-terms` | Portal-Login inkl. Bestätigung der Nutzungsbedingungen; speichert lokalen Session-State |
| `wifionice checkin --dry-run` | zeigt nur, was gesendet würde (kein Netzwerk) |
| `wifionice status` | Portal erreichbar? Session aktiv? (CNA-API, Legacy-Fallback) |
| `wifionice speed` | Zuggeschwindigkeit in km/h aus dem Onboard-ICE-Portal (kein Bandbreitentest; nur im Zug erreichbar) |
| `wifionice logout` | Portal-Logoff (`POST /cna/logoff`, best effort) und lokaler Session-State |
| `wifionice config` | zeigt die aufgelöste Konfiguration inkl. Quellen |
| `wifionice version` | Paketversion |

Beispiele:

```bash
wifionice status --json
wifionice checkin --accept-terms
wifionice checkin --accept-terms --dry-run --json
wifionice speed --json
wifionice logout --dry-run
```

### checkin und AGB

Der Portal-Login bestätigt die Nutzungsbedingungen des WIFIonICE-Portals. Deshalb verlangt ein echter Checkin explizit `--accept-terms` (sonst Exit-Code 1). `--dry-run` zeigt den geplanten Request-Ablauf, ohne etwas zu senden.

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg |
| 1 | Ungültige Eingabe (Flags, Argumente, Validierung); argparse-Fehler landen hier, nicht bei 2 |
| 2 | Portal hat den Checkin abgelehnt (Auth/AGB) bzw. HTTP 401/403 |
| 3 | Netzwerk-/Transportfehler (DNS, Timeout, HTTP 5xx) |
| 4 | Antwort oder Datei nicht parsebar (JSON, Config, State) |
| 130 | Abbruch (Ctrl-C) oder EOF |

Implementierung: `wifionice_cli.exit_codes`, `wifionice_cli.errors.ArgumentParser`.

## Genutzte Portal-Endpunkte

Recherchiert und gegen Open-Source-Referenzen abgeglichen (siehe unten). Es wurden keine Endpunkte erfunden.

| Flow | Request | Antwort |
|------|---------|---------|
| CNA-Checkin (aktuell) | `POST {base}/cna/logon`, Body `{}`, Header `Content-Type: application/json`, `X-Requested-With: XMLHttpRequest`, `X-Csrf-Token: csrf`, `Referer: {base}/cna/` | JSON mit `result: "success"` |
| CNA-Status | `GET {base}/cna/wifi/user_info` | JSON, u. a. `result.authenticated` (`"1"`/`"0"`) |
| CNA-Logoff | `POST {base}/cna/logoff`, Body `{}`, gleiche Header wie CNA-Checkin | JSON mit `result: "success"` |
| Legacy-Fallback (bei HTTP 404) | `GET {base}/de/` setzt ein `csrf`-Cookie, dann `POST {base}/de/` mit `login=true&CSRFToken=<token>` | HTML ohne `id="accept"`-Formular = eingeloggt |
| Zuggeschwindigkeit | `GET {iceportal}/api1/rs/status` | JSON, u. a. `speed` (km/h), `servicelevel`, `connection` |

Referenzen: [openwrt travelmate `wifibahn.login`](https://github.com/openwrt/packages/blob/master/net/travelmate/files/wifibahn.login), [binarynoise/CaptivePortalAutoLogin `DBWifi.kt`](https://github.com/binarynoise/CaptivePortalAutoLogin), [felix-zenk/onboardapis](https://github.com/felix-zenk/onboardapis), [derhuerst-Gist zum ICE-Portal](https://gist.github.com/derhuerst/bdca32a50c7ca4a004cee90745a7f68c).

## Konfiguration

Präzedenz: Umgebungsvariablen > Konfigurationsdatei (`~/.config/wifionice/config.json`) > Defaults. Es gibt keine Zugangsdaten; Keyring wird nicht benötigt.

| Variable | Default | Zweck |
|----------|---------|-------|
| `WIFIONICE_BASE_URL` | `https://wifi.bahn.de` | Basis-URL des Captive Portals |
| `WIFIONICE_ICEPORTAL_URL` | `https://iceportal.de` | Onboard-ICE-Portal für `speed` |
| `WIFIONICE_STATE` | `~/.local/state/wifionice/session.json` | Pfad des lokalen Session-States |
| `WIFIONICE_TIMEOUT` | `5` | HTTP-Timeout in Sekunden |
| `WIFIONICE_CONFIG` | `~/.config/wifionice/config.json` | Pfad der Konfigurationsdatei |

Konfigurationsdatei (JSON), alles optional:

```json
{"base_url": "https://wifi.bahn.de", "iceportal_url": "https://iceportal.de", "timeout": 5}
```

## State

- `checkin` schreibt den lokalen Session-State atomar (Temp-Datei + Rename) und ohne Secrets: Basis-URL, Methode, Zeitpunkt.
- `--dry-run` führt keine Schreibzugriffe aus.
- `logout` versucht `POST /cna/logoff` (best effort, Fehler nur als Warning); der lokale State wird immer entfernt.

## Tests

Alle Tests laufen offline. `tests/fake_server.py` ist ein stdlib-HTTP-Server (`ThreadingHTTPServer`) mit Request-Recorder, der den echten Flow nachbildet: Portal-Seite, AGB-Formular, CSRF-Cookie, Checkin-POST, Status-JSON und ICE-Portal-Status.

```bash
uv run --extra dev pytest -q
```

Contract-Tests (`tests/test_portal_contract.py`) decken Happy Path und Fehlerpfade ab: Netzwerk down → 3, kaputtes JSON → 4, fehlende/falsche Argumente → 1, Portal lehnt ab → 2, State/dry-run schreibt nichts, JSON-Envelope ist genau ein Objekt. `tests/test_readme_commands.py` hält README-Beispiele und `--help` synchron.

## Live-Check

Stand 2026-10-13, Heimnetz, **ohne** Zug-WLAN; read-only (kein echter Checkin, keine Dateneingabe), ~8 Requests:

| Endpoint | Ergebnis | Bedeutung |
|----------|----------|-----------|
| `https://wifi.bahn.de/` | `NXDOMAIN` (öffentliches DNS) | Portal-Domain existiert nur im Zugnetz |
| `https://login.wifionice.de/` | `NXDOMAIN` | ebenso |
| `https://iceportal.de/` | HTTP 200, ICE-Portal-Seite (84 KB) | Host öffentlich erreichbar |
| `https://iceportal.de/api1/rs/status` | HTTP 200, leerer Body (0 Bytes, `application/octet-stream`) | verwertbare JSON-Daten nur im Zug |

Fazit: `checkin` und `status` sind nur im WIFIonICE-Netz vollständig testbar; von zu Hause greift erwartetes Captive-Portal-Verhalten (kein DNS für die Portal-Hosts). `speed` liefert erst im Zug strukturierte Daten — deshalb bricht die CLI außerhalb des Zugnetzes sauber mit Exit-Code 4 ab, statt Werte zu erfinden. Ein echter Checkin wurde nicht ausgeführt.

## Grenzen

- Echter Checkin, AGB-Schritt und aktive Session sind nur im Zug verifizierbar (siehe Live-Check).
- `speed` ist die Zuggeschwindigkeit in km/h aus dem Onboard-Portal (`measurement`: `train_speed_kmh`), keine Bandbreitenmessung. Ein optionaler Bandbreiten-Check (`speed --bandwidth`) ist bewusst nicht vorgesehen; die CLI lehnt `--bandwidth` mit Exit-Code 1 ab.
- `logout` meldet mit `--json` `portal_logoff: true/false`; ohne erreichbares Portal bleibt Exit 0, lokaler State wird trotzdem gelöscht.
- Die Portal-API ist nicht versioniert und kann sich ändern; die Legacy-Variante dient als Fallback.
