# UX-Spec: wifionice

`wifionice` prüft und steuert das WIFIonICE-Captive-Portal im Zug. Der Checkin
bestätigt die Nutzungsbedingungen des Portals, deshalb fragt die CLI im Terminal
vor jedem Request nach. Zugangsdaten werden weder benötigt noch gespeichert.

Die Basis-URL des Captive Portals ist über `WIFIONICE_BASE_URL` überschreibbar
(Default `https://wifi.bahn.de`, für den Fake-Server in Tests). `speed` liest
separat vom Onboard-ICE-Portal, dessen URL über `WIFIONICE_ICEPORTAL_URL`
gesetzt wird (Default `https://iceportal.de`). Credential-Env gibt es nicht.

```ux-meta
{"tool": "wifionice",
 "install": "pipx install git+https://github.com/smlfg/wifionice-cli",
 "base_url_env": "WIFIONICE_BASE_URL",
 "credential_env": []}
```

## Installieren und Portalstatus prüfen

Der Status liest `GET /cna/wifi/user_info` (aktueller CNA-Flow). Antwortet das
Portal dort mit HTTP 404, wird lesend `GET /de/` als Legacy-Fallback geprüft.
Ein aktives Zugnetz ist für den echten Aufruf nötig; im Test antwortet der
Fake-Server.

```ux-session
$ pipx install git+https://github.com/smlfg/wifionice-cli
$ wifionice status
<~ Portal: http://127\.0\.0\.1:\d+
< Erreichbar: ja
< Session: nicht angemeldet
! exit 0
```

## Zuggeschwindigkeit lesen

Die Geschwindigkeit kommt aus `GET /api1/rs/status` des Onboard-ICE-Portals und
ist die Zuggeschwindigkeit in km/h, keine Bandbreitenmessung. Ausserhalb des
Zuges liefert der Endpunkt einen leeren Body; dann erklärt die CLI den Fehler
mit Exit-Code 4, statt einen Wert zu erfinden.

```ux-session
$ wifionice speed
< Zuggeschwindigkeit: 109 km/h
< Servicelevel: AVAILABLE_SERVICE
< Verbindung: ja
! exit 0
```

## Checkin verbindlich durchführen

Der Checkin zeigt zuerst Portal-URL und AGB-Hinweis. Danach fragt er auf stderr
`Checkin verbindlich? [j/N]` (Default Nein). Erst nach `j` sendet er alle
Requests des Checkins; bei `N` endet er vor jedem schreibenden Request. Ohne
TTY und ohne `--confirm`/`--yes` bricht er vor jedem Request ab. `--accept-terms`
bleibt die explizite Zustimmung für nicht-interaktive Aufrufe.

Primär wird `POST /cna/logon` mit JSON `{}` und den CNA-Headern gesendet
(`X-Csrf-Token: csrf`, `X-Requested-With: XMLHttpRequest`, Referer `{base}/cna/`).
Antwortet das Portal dort mit HTTP 404, folgt der Legacy-Fallback (siehe unten).

```ux-session
$ wifionice checkin
<~ Portal: http://127\.0\.0\.1:\d+
< AGB: Der Checkin bestätigt die Nutzungsbedingungen des WIFIonICE-Portals.
< Checkin verbindlich? [j/N]
> j
< Checkin erfolgreich (Methode: cna).
! exit 0
```

## Lesende Routen

Alle Routen, die die Sitzungen gegen den Fake-Server brauchen. Der
Legacy-Login-Einstieg ist ein lesendes `GET /de/`; der zugehörige schreibende
POST steht im Abschnitt zum Legacy-Fallback.

```ux-routes
[{"method":"GET","path":"/cna/wifi/user_info","response":"tests/fixtures/ux/cna_user_info.json","status":200,"content_type":"application/json; charset=utf-8"},
 {"method":"GET","path":"/de/","response":"tests/fixtures/ux/legacy_login.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/api1/rs/status","response":"tests/fixtures/ux/iceportal_status.json","status":200,"content_type":"application/json; charset=utf-8"}]
```

## Formularschritte der schreibenden Aktion

Der Checkin ist gegen das echte Portal ausserhalb des Zugnetzes nicht lesend
erreichbar. Die Schritte sind deshalb aus der dokumentierten Endpunkt-Tabelle
in `README.md` nachgebaut und als `synthetisch` markiert. Der verbindliche
Schritt ist `POST /cna/logon`; danach ist der Checkin abgeschlossen.

```ux-formsteps
[{"id":"cna_logon","method":"POST","path":"/cna/logon","sends":[],"response":"tests/fixtures/ux/cna_logon_success.json","final":true,"live":"synthetisch"}]
```

### Legacy-Fallback (bei HTTP 404 auf `/cna/logon`)

Der Legacy-Flow ist eine Alternative zum CNA-Schritt, kein zusätzlicher Schritt
im selben Lauf. Er wird deshalb nicht als linearer `ux-formsteps`-Eintrag
geführt: Eine lineare Liste würde verlangen, dass jeder Checkin CNA **und**
Legacy sendet.

| Reihenfolge | Request | Felder | Wirkung |
|---|---|---|---|
| 1 (lesend) | `GET /de/` | – | setzt das `csrf`-Cookie, liefert das Formular mit `id="accept"` |
| 2 (verbindlich) | `POST /de/` | `login=true`, `CSRFToken=<token aus Cookie oder Hidden-Feld>` | Checkin, finaler Schritt des Falls |

Beide Requests sind aus der Endpunkt-Tabelle in `README.md` und den
Open-Source-Referenzen bekannt, aber live nicht gesehen (`synthetisch`).
