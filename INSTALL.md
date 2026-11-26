# Installation

Diese Anleitung beschreibt die automatische und manuelle Installation auf Debian-basierten Systemen. Das Installationsskript lädt Programm und Beispielkonfiguration aus dem offiziellen Repository, legt einen eigenen Dienstbenutzer an und richtet Dateirechte sowie den systemd-Dienst ein.

## Automatische Installation

Voraussetzungen: Debian/Ubuntu mit Python 3, systemd und `curl` oder `wget`. Das Skript muss mit Root-Rechten laufen. Es installiert keine Pakete.

```sh
curl -fsSLO https://raw.githubusercontent.com/TeamO82/Senec-Proxy/main/install.sh
less install.sh
sudo bash install.sh
```

Das Skript fragt interaktiv nach dem SENEC-Host. Alternativ kann der Host nicht-interaktiv übergeben werden:

```sh
sudo env SENEC_HOST=192.168.0.171 bash install.sh
```

Optional lässt sich der SENEC-Port mit `SENEC_PORT` setzen oder der Quell-Branch bzw. Tag mit `SENEC_PROXY_VERSION` auswählen.

Das Skript überschreibt eine bereits vorhandene Konfiguration nicht. Die Standardkonfiguration bindet den Proxy an `127.0.0.1`. Für Zugriff aus dem LAN ändern Sie `listen_host` in `/usr/local/senec-proxy/senec-proxy.conf` bewusst auf `0.0.0.0` und begrenzen den Zugriff über Ihre Firewall. Der Proxy bietet keine eingebaute Anmeldung.

## Manuelle Installation

> Diese Anleitung führt durch die manuelle Installation auf Debian-basierten Systemen. Die Befehle nehmen Änderungen am Zielsystem vor, wenn sie dort ausgeführt werden.

## 1. Python und systemd prüfen

```sh
python3 --version
systemctl --version
```

Das Programm nutzt nur die Python-Standardbibliothek. `systemctl` ist für den hier beschriebenen Dienstbetrieb erforderlich.

## 2. Installationsordner und Dateien anlegen

```sh
sudo install -d -m 0755 /usr/local/senec-proxy
sudo install -m 0644 senec-proxy.py /usr/local/senec-proxy/senec-proxy.py
sudo install -m 0644 senec-proxy.conf.example /usr/local/senec-proxy/senec-proxy.conf
```

Die Beispieldatei `senec-proxy.conf.example` muss vor dem Kopieren mit den eigenen Werten angepasst werden. Das Programm erwartet die Datei am festen Zielpfad `/usr/local/senec-proxy/senec-proxy.conf`.

## 3. Konfiguration bearbeiten

```sh
sudo mcedit /usr/local/senec-proxy/senec-proxy.conf
```

`mcedit` ist der Editor des Pakets Midnight Commander und möglicherweise nicht installiert. Wenn er fehlt, einen bereits vorhandenen Texteditor verwenden.

Mindestens `host` unter `[SENEC]` eintragen. `listen_host = 127.0.0.1` beschränkt Zugriffe auf das lokale System. `0.0.0.0` macht den Proxy über alle IPv4-Schnittstellen erreichbar; das Programm bietet keine Authentifizierung. `ssl_verify = false` deaktiviert die Prüfung des SENEC-TLS-Zertifikats.

## 4. Logdatei vorbereiten

Das Programm schreibt selbst nach `/usr/local/senec-proxy/senec-proxy.log`. Der Dienstbenutzer muss den Ordner beschreiben können. Für einen einfachen ersten Betrieb als root würde das Verzeichnis dem root-Benutzer gehören. Für einen dedizierten Dienstbenutzer müssen Eigentümer und Rechte passend eingerichtet werden.

```sh
sudo touch /usr/local/senec-proxy/senec-proxy.log
```

## 5. systemd-Unit erstellen

Der Installer erstellt die systemd-Unit automatisch. Bei manueller Installation passt der folgende Vorschlag zum festen Programmpfad; `User=` und `Group=` bei einem dedizierten Dienstkonto ergänzen und die Schreibrechte für die Logdatei sicherstellen.

```sh
sudo mcedit /etc/systemd/system/senec-proxy.service
```

Vorgeschlagener Inhalt:

```ini
[Unit]
Description=SENEC lala.cgi cache proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/usr/local/senec-proxy
ExecStart=/usr/bin/python3 /usr/local/senec-proxy/senec-proxy.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Der Dienst läuft mit dieser Beispiel-Unit als root, weil kein `User=` gesetzt ist. Für dauerhaften Betrieb sollte ein eigener Systembenutzer mit gezielten Schreibrechten eingerichtet und in der Unit eingetragen werden.

## 6. Dienst starten und prüfen

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now senec-proxy.service
sudo systemctl status senec-proxy.service
curl -sS http://127.0.0.1:8765/status
```

Bei einer abweichenden Listenadresse oder einem anderen Port die URL entsprechend anpassen. Der Dienst nimmt Verbindungen erst an, nachdem der erste SENEC-Abschnitts- und Datenabruf abgeschlossen ist.

## 7. Fehler ansehen

```sh
sudo tail -n 50 /usr/local/senec-proxy/senec-proxy.log
sudo journalctl -u senec-proxy.service -n 50 --no-pager
```

Die Anwendung protokolliert in die genannte Datei; systemd zeigt zusätzlich Start- und Prozessmeldungen im Journal.


