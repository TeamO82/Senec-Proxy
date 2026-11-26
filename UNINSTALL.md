# Deinstallation

> **Achtung:** Die folgenden Schritte stoppen den Dienst und löschen Installationsdateien. Vor dem Entfernen sicherstellen, dass die genannten Pfade ausschließlich zu diesem Proxy gehören.

## 1. Dienst stoppen und Autostart deaktivieren

```sh
sudo systemctl disable --now senec-proxy.service
```

## 2. systemd-Unit entfernen

```sh
sudo rm /etc/systemd/system/senec-proxy.service
sudo systemctl daemon-reload
sudo systemctl reset-failed senec-proxy.service
```

## 3. Programm, Konfiguration und Log entfernen

Die Konfiguration kann lokale Netzwerkangaben enthalten. Vorher bei Bedarf sichern. Der folgende Befehl löscht das gesamte Proxy-Verzeichnis einschließlich Logdatei:

```sh
sudo rm -r /usr/local/senec-proxy
```

## 4. Ergebnis kontrollieren

```sh
systemctl status senec-proxy.service
```

Der Dienst sollte als nicht gefunden oder nicht geladen erscheinen. Falls bei der Installation ein eigener Systembenutzer angelegt wurde, kann er nach Prüfung entfernt werden. Die gezeigte Installationsskizze legt keinen solchen Benutzer an.


