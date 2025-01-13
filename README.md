# ePapier - Python

Repozytorium odpowiedzialne za część projektu związaną z językiem Python, wykorzystywaną do obsługi inteligentnego ekranu typu ePapier.

> [!IMPORTANT]
> Projekt jest w fazie rozwoju, przewiduje się dalsze usprawnienia, a bieżąca wersja może zawierać błędy.

## Technologie

Projekt bazuje na języku Python, z wykorzystaniem biblioteki do obsługi ekranów ePapier firmy Waveshare, dostępnej [tutaj](https://github.com/waveshareteam/e-Paper). Wykorzystywany jest także prosty serwer Flask, który umożliwia wymuszenie pełnej aktualizacji ekranu oraz aktualizację adresu IP urządzenia w sieci lokalnej na platformie Cloudflare (co jest niezbędne do prawidłowego działania usług Google i Spotify).

## Instalacja

1. W pierwszej kolejności na urządzeniu Raspberry Pi należy włączyć interfejs SPI, co można zrobić za pomocą polecenia:

   ```bash
   sudo raspi-config
   ```

   W menu ustawień interfejsów należy włączyć interfejs SPI i zrestartować urządzenie.

2. Następnie wykonaj poniższe komendy:

   ```bash
   sudo apt update
   sudo apt install python3-pip
   sudo apt install chromium-chromedriver
   ```

3. Zainstaluj wymagane biblioteki:

   ```bash
   sudo pip3 install -r requirements.txt --break-sy
   ```

4. Na koniec uruchomienie programu:

   ```bash
   sudo python app.py
   ```

   Można także do uruchomienia w tle użyć `screen`

   ```bash
   sudo screen python app.py
   ```

   Do uruchomienia programu w tle na autostarcie systemu można skorzystać z skryptu `autostarh.sh`:

   ```bash
   sudo ./autostart.sh
   ```

## Czyszczenie ekranu

W celu awaryjnego czyszczenia (gdyby program przestał w niespodziewany sposób działać) ekranu stworzono plik `clear_screen.py`. Uruchomienie tego pliku pozwala wyczyścić ekran ePapier.

## Zmienne środowiskowe

Aby usługa aktualizacji adresu IP w serwisie Cloudflare działała poprawnie, należy utworzyć plik `.env` na podstawie wzoru `.env.example` i uzupełnić go następującymi informacjami:

    CLOUDFLARE_API_TOKEN= Klucz API wygenerowany w Cloudflare
    CLOUDFLARE_ZONE_ID= ID Strefy
    CLOUDFLARE_RECORD_ID= ID rekordu utworzonego w Cloudflare
    CLOUDFLARE_DOMAIN= nazwa domeny, którą należy zaktualizować (np. local.example.com)
