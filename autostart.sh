#!/bin/bash

# Sprawdzanie, czy skrypt jest uruchamiany jako root
if [ "$EUID" -ne 0 ]; then
  echo "Prosze uruchomic ten skrypt jako root lub uzyj sudo."
  exit 1
fi

# Zmienne
SERVICE_NAME="epapier_inzynierka"
SCRIPT_PATH="$(pwd)/app.py"  # Sciezka do skryptu w tym samym folderze
WORKING_DIR="$(pwd)"        # Katalog roboczy to biezacy folder
PYTHON_PATH="/usr/bin/python3"               # Sciezka do interpretera Pythona

# Sprawdzanie, czy podany plik skryptu istnieje
if [ ! -f "$SCRIPT_PATH" ]; then
  echo "Plik skryptu nie zostal znaleziony: $SCRIPT_PATH"
  exit 1
fi

# Tworzenie pliku jednostki systemd
UNIT_FILE="/etc/systemd/system/$SERVICE_NAME.service"
echo "Tworzenie pliku jednostki systemd: $UNIT_FILE"
cat <<EOL > "$UNIT_FILE"
[Unit]
Description=Usluga uruchamiajaca app.py jako root dla ekranu epapier inzynierka
After=network.target

[Service]
ExecStart=$PYTHON_PATH $SCRIPT_PATH
WorkingDirectory=$WORKING_DIR
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Zaladowanie nowej konfiguracji systemd
echo "Zaladowanie nowej konfiguracji systemd..."
systemctl daemon-reload

# Wlaczenie uslugi do autostartu
echo "Wlaczenie uslugi $SERVICE_NAME do autostartu..."
systemctl enable "$SERVICE_NAME"

# Uruchomienie uslugi
echo "Uruchamianie uslugi $SERVICE_NAME..."
systemctl start "$SERVICE_NAME"

# Wyswietlenie statusu uslugi
echo "Wyswietlanie statusu uslugi $SERVICE_NAME:"
systemctl status "$SERVICE_NAME"
