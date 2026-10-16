# MiniScreenShot 1.1.4

<img src="assets/capture-frame.png" alt="Logo MiniScreenShot" width="112">

Przenośna aplikacja do zrzutów ekranu dla Windows. Stworzone przez Szymona Bartosa.

## Pobieranie

**[Pobierz MiniScreenShot dla Windows](https://github.com/szymon-bartos/MiniScreenShot/releases/download/v1.1.4/MiniScreenShot_v1.1.4.exe)**

Pobierz plik EXE i uruchom — bez instalowania Pythona. Wszystkie opublikowane wersje są dostępne w [wydaniach GitHub](https://github.com/szymon-bartos/MiniScreenShot/releases). Warunki korzystania znajdziesz w [LICENSE.txt](LICENSE.txt) oraz w aplikacji pod przyciskiem „Informacje”.

## Funkcje

- Zrzut całego ekranu, wybranego okna lub zaznaczonego obszaru.
- Przechwytywanie przewijanej zawartości w pionie i poziomie, z łączeniem fragmentów podczas jednego przejścia.
- Automatyczne zmniejszanie bardzo dużych zrzutów do około 24 megapikseli lub mniej.
- Podgląd z powiększaniem, strzałkami i przewijaniem dwoma palcami na touchpadzie.
- Przycinanie, ołówek, półprzezroczysty mazak, wybór koloru i grubości oraz cofanie oznaczeń.
- Zapis PNG i kopiowanie obrazu do schowka.
- Wybór okna i odświeżanie jego listy bezpośrednio w głównym panelu.

## Uruchomienie z kodu i budowanie

Wymagany jest Windows oraz Python 3.11 lub nowszy z Tkinterem.

1. Uruchom `start_app.bat`, aby uruchomić aplikację z kodu.
2. Uruchom `build_advanced_exe.bat`, aby zbudować `dist\MiniScreenShot_v1.1.4.exe`. Skrypt przygotowuje środowisko i instaluje zależności.

Głównym plikiem aplikacji jest `app_advanced.py`. Szczegółowa obsługa, ograniczenia przewijania i polecenia sprawdzające są opisane w [README_advanced.md](README_advanced.md).

## Licencja

Autor udziela użytkownikowi bezpłatnej, niewyłącznej licencji na korzystanie z programu w celach prywatnych i komercyjnych. Zabrania się modyfikowania, dekompilacji, inżynierii wstecznej kodu programu oraz jego sprzedaży lub czerpania bezpośrednich zysków z jego dystrybucji bez zgody autora.
