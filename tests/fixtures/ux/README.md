# UX-Fixtures: wifionice-cli

Herkunft und Anonymisierung der Dateien in diesem Verzeichnis. Es sind keine
Zugangsdaten, Konten oder echten Personendaten enthalten.

| Datei | Herkunft | Anmerkung |
|---|---|---|
| `cna_user_info.json` | synthetisch | Antwortform von `GET /cna/wifi/user_info` aus der Endpunkt-Tabelle in `README.md`; Werte gekürzt und anonymisiert. |
| `cna_logon_success.json` | synthetisch | Erfolgsantwort von `POST /cna/logon` aus der Endpunkt-Tabelle in `README.md`. |
| `legacy_login.html` | synthetisch | Login-Seite des Legacy-Flows (`/de/`) mit `id="accept"`, verstecktem `CSRFToken` und `login=true`; live nur im Zug erreichbar. |
| `legacy_authenticated.html` | synthetisch | Seite nach erfolgreichem Legacy-Login ohne `id="accept"`-Formular; dient der Status-Erkennung. |
| `iceportal_status.json` | synthetisch | Antwortform von `GET /api1/rs/status` aus `README.md` und den Contract-Tests. Live lieferte `https://iceportal.de/api1/rs/status` am 2026-11-04 ausserhalb des Zuges HTTP 200 mit leerem Body (`application/octet-stream`), deshalb keine echte Messung. |

Live-Erkundung: `scratch/live/NOTIZEN.md` (nicht Teil des Repos).
