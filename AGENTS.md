# Agent notes (wifionice)

CLI für das WIFIonICE-Captive-Portal. Diese Datei ergänzt die Template-Muster (exit_codes, errors, state, config, url_util, json_util, validation) um die Domänenregeln.

1. **Endpunkte nicht erfinden** — Nutze nur die in `README.md` dokumentierten Flows (`/cna/logon`, `/cna/logoff`, `/cna/wifi/user_info`, Legacy `/de/`, ICE-Portal `/api1/rs/status`) und aktualisiere die Endpunkt-Tabelle, wenn sich etwas ändert. `src/wifionice_cli/portal.py` ist die einzige Stelle mit HTTP-Aufrufen.
2. **AGB** — Ein echter `checkin` erfordert `--accept-terms` (Exit 1 sonst). `--dry-run` zeigt den geplanten Ablauf und macht weder Netzwerk noch Schreibzugriffe.
3. **Exit-Codes** — 0 ok, 1 Eingabe, 2 Portal-Ablehnung/Auth, 3 Netz, 4 Parse, 130 Abbruch. Transportfehler werden in `http_util.py` zentral gemappt.
4. **State** — `state.save_state(..., dry_run=)`; keine Secrets in State/Ausgaben/Tracebacks. `logout` ruft best effort `POST /cna/logoff` auf und löscht lokal.
5. **Tests offline** — Fake-Portal `tests/fake_server.py` (`ThreadingHTTPServer`, Request-Recorder); keine echten Requests in Tests. README-Beispiele müssen in `--help` stehen (`tests/test_readme_commands.py`).
6. **Doku** — `docs/QA-CHECKLIST.md` vor Abschluss durchgehen; README (deutsch) mit `--help` synchron halten.
