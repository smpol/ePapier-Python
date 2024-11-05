# ePapier - Python

Repozytorium odpowiedzialne za część projektu związaną z językiem Python, wykorzystywaną do obsługi inteligentnego ekranu typu ePapier.

> **Uwaga**: Projekt jest w fazie rozwoju, przewiduje się dalsze usprawnienia, a bieżąca wersja może zawierać błędy.

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
   sudo apt-get update
   sudo apt-get install python3-pip
   sudo apt-get install python3-pil
   sudo apt-get install python3-numpy
   ```

3. Utwórz środowisko wirtualne dla Pythona:

   ```bash
   python -m venv env
   ```

4. Aktywuj środowisko:

   ```bash
   source env/bin/activate
   ```

5. Zainstaluj wymagane biblioteki:

   ```bash
   pip install -r requirements.txt
   ```

6. Na koniec uruchom program:

   ```bash
   sudo python screen_update.py
   ```

   Można także do uruchomienia w tle użyć `screen`

   ```bash
   sudo screen python screen_update.py
   ```

## Czyszczenie ekranu

W celu awaryjnego czyszczenia (gdyby program przestał w niespodziewany sposób działać) ekranu stworzono plik `clear_screen.py`. Uruchomienie tego pliku pozwala wyczyścić ekran ePapier.

## Zmienne środowiskowe

Aby usługa aktualizacji adresu IP w serwisie Cloudflare działała poprawnie, należy utworzyć plik `.env` na podstawie wzoru `.env.example` i uzupełnić go następującymi informacjami:

    CLOUDFLARE_API_TOKEN= Klucz API wygenerowany w Cloudflare
    CLOUDFLARE_ZONE_ID= ID Strefy
    CLOUDFLARE_RECORD_ID= ID rekordu utworzonego w Cloudflare
    CLOUDFLARE_DOMAIN= nazwa domeny, którą należy zaktualizować (np. local.example.com)
