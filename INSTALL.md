# Installation

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

Die Unit-Datei ist im Projektordner nicht enthalten. Der folgende Vorschlag passt zum festen Programmpfad; `User=` und `Group=` bei einem dedizierten Dienstkonto ergänzen und die Schreibrechte für die Logdatei sicherstellen.

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


