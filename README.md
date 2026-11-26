# SENEC lala.cgi Cache-Proxy

Der Proxy fragt die SENEC-Schnittstelle `lala.cgi` regelmäßig ab und stellt die zuletzt erfolgreich geladenen Daten über eine lokale HTTP-Schnittstelle bereit. Er verwendet ausschließlich die Python-Standardbibliothek.

## Voraussetzungen

- Linux mit Python 3
- Für den empfohlenen Dienstbetrieb: systemd
- Netzwerkverbindung vom Proxy zum SENEC und von den Clients zum Proxy

Es werden keine zusätzlichen Python-Pakete benötigt.

## Dateien und feste Pfade

Das Programm verwendet fest diese Pfade:

- `/usr/local/senec-proxy/senec-proxy.py` – Programm
- `/usr/local/senec-proxy/senec-proxy.conf` – Konfiguration
- `/usr/local/senec-proxy/senec-proxy.log` – Protokolldatei
- `/etc/systemd/system/senec-proxy.service` – vorgesehene systemd-Unit

Die Konfigurationsdatei wird nicht über ein Kommandozeilenargument ausgewählt. Sie muss unter dem oben genannten Namen und Pfad liegen. Das Verzeichnis muss vor dem Start angelegt sein, damit die Logdatei geschrieben werden kann.

## Konfiguration

Die Datei ist im INI-Format aufgebaut:

```ini
[SENEC]
host = senec.local
port = 443
ssl_verify = false
poll_interval = 10
section_refresh_interval = 300
timeout = 5

[PROXY]
listen_host = 127.0.0.1
listen_port = 8765
```

| Einstellung | Bedeutung | Standard im Programm |
|---|---|---|
| `SENEC.host` | SENEC-Hostname oder IP-Adresse; erforderlich | keiner |
| `SENEC.port` | HTTPS-Port des SENEC | `443` |
| `SENEC.ssl_verify` | TLS-Zertifikat prüfen | `false` |
| `SENEC.poll_interval` | Abstand zwischen Datenabfragen in Sekunden | `10` |
| `SENEC.section_refresh_interval` | Abstand für dynamische Abschnittserkennung in Sekunden | `300` |
| `SENEC.timeout` | Zeitlimit pro SENEC-Anfrage in Sekunden | `5` |
| `PROXY.listen_host` | Adresse, an der der HTTP-Server lauscht | `0.0.0.0` |
| `PROXY.listen_port` | HTTP-Port des Proxys | `8765` |

**Netzwerkzugriff:** `0.0.0.0` bindet den Dienst an alle IPv4-Netzwerkschnittstellen. Der Proxy hat keine eingebaute Anmeldung oder Zugriffskontrolle. Für lokalen Zugriff `127.0.0.1` setzen; bei Zugriff aus dem LAN die Erreichbarkeit gezielt per Netz und Firewall begrenzen.

**TLS:** In der mitgelieferten Konfiguration ist `ssl_verify = false` gesetzt. Dann wird das SENEC-Zertifikat nicht geprüft. Wenn der SENEC ein vertrauenswürdiges Zertifikat bereitstellt, `true` setzen. Bei selbstsignierten Zertifikaten kann die Prüfung andernfalls fehlschlagen.

## Schnittstellen

### `GET /status`

Liefert JSON mit Betriebszustand und Cache-Metadaten. Felder sind `status` (`starting` oder `ok`), `senec_host`, `senec_port`, `poll_interval`, `section_refresh_interval`, `cache_age`, `last_success`, `last_error`, `sections`, `known_sections` und `last_section_refresh`.

```sh
curl -sS http://127.0.0.1:8765/status
```

### `GET /cache`

Liefert den gesamten Cache als JSON. Solange noch kein erfolgreicher Abruf vorliegt, antwortet der Endpunkt mit HTTP 503 und `{}`.

```sh
curl -sS http://127.0.0.1:8765/cache
```

### `POST /lala.cgi`

Nimmt eine JSON-Anfrage im SENEC-Format entgegen. Ein leerer Abschnittsinhalt `{}` fordert alle gecachten Variablen des Abschnitts an; mit Schlüsseln werden einzelne Variablen angefordert.

```sh
curl -sS --max-time 10 -X POST \
  -H 'Content-Type: application/json' \
  -d '{"ENERGY":{"GUI_BAT_DATA_POWER":""}}' \
  http://127.0.0.1:8765/lala.cgi
```

Ein unbekannter Abschnitt ergibt `{"OBJECT_NOT_FOUND":""}` für diesen Abschnitt. Eine unbekannte Variable ergibt den Wert `"VARIABLE_NOT_FOUND"`. Ungültiges JSON wird mit HTTP 400 gemeldet; unbekannte Pfade mit HTTP 404.

## Cache und Fehlerverhalten

Beim Start erkennt der Proxy zunächst SENEC-Abschnitte und lädt Daten, bevor er Clientverbindungen annimmt. Anschließend pollt er regelmäßig. Ein erfolgreicher Abruf ersetzt den Cache vollständig. Bei einem fehlgeschlagenen Abruf bleibt der letzte erfolgreiche Cache erhalten; `/status` zeigt den letzten Fehler und das Alter der Daten. Abschnittsnamen werden dynamisch neu ermittelt.

## Protokoll und Dienst

Das Programm schreibt nach `/usr/local/senec-proxy/senec-proxy.log`. Der Prozess benötigt dafür Schreibrechte. Dienststeuerung und genaue systemd-Unit stehen in der Installationsanleitung.


