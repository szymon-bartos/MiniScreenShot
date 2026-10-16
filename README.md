# MiniScreenShot 1.1.5

<img src="assets/capture-frame.png" alt="Logo MiniScreenShot" width="112">

Przenośna aplikacja do zrzutów ekranu dla Windows. Stworzone przez Szymona Bartosa.

## Pobieranie

**[Pobierz MiniScreenShot dla Windows](https://github.com/szymon-bartos/MiniScreenShot/releases/download/v1.1.5/MiniScreenShot_v1.1.5_windows.zip)**

Rozpakuj cały ZIP, a następnie uruchom `MiniScreenShot_v1.1.5.exe` z rozpakowanego folderu. Katalog `_internal` musi pozostać obok EXE. Python ani instalator nie są potrzebne. Wszystkie opublikowane wersje są dostępne w [wydaniach GitHub](https://github.com/szymon-bartos/MiniScreenShot/releases). Warunki korzystania znajdziesz w [LICENSE.txt](LICENSE.txt) oraz w aplikacji pod przyciskiem „Informacje”.

Do wydania dołączona jest suma SHA-256 archiwum. Potwierdza zgodność pobranego pliku z publikacją; nie zastępuje skanowania antywirusem ani podpisu cyfrowego.

Od 1.1.5 biblioteki są dostarczane w folderze aplikacji: program nie rozpakowuje ich przy każdym uruchomieniu. Cache trafia do `C:\MiniScreenShot\cache`; jeśli katalog jest niedostępny, do `%LOCALAPPDATA%\MiniScreenShot\cache`. Limit wynosi 512 MB na sesję. Pliki fragmentów są usuwane po złożeniu zrzutu, pliki dużego podglądu po jego zamknięciu, a pozostała sesja przy wyjściu. Kolejny start usuwa pozostałości po przerwanych sesjach, zachowując pliki uruchomionych kopii programu. Logi w sąsiednim folderze `logs` zajmują najwyżej około 1,5 MB.

### Status zabezpieczeń

Dla wersji 1.1.4 zgłoszono alarm przy uruchamianiu: `Behavior:Win32/DefenseEvasion.A!ml`. Zmiana sposobu pakowania w 1.1.5 nie jest rozstrzygnięciem tego zgłoszenia przez Microsoft. Aplikacja nie ma podpisu Authenticode, więc SmartScreen może również ostrzegać o nieznanym wydawcy. Jeśli Defender zablokuje plik, pozostaw go w kwarantannie i zgłoś szczegóły; nie wyłączaj ochrony ani nie dodawaj wyjątków. Plik można przekazać do [analizy Microsoft jako producent oprogramowania](https://www.microsoft.com/en-us/wdsi/filesubmission).

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
2. Uruchom `build_advanced_exe.bat`, aby zbudować `dist\MiniScreenShot_v1.1.5\MiniScreenShot_v1.1.5.exe` i pełną paczkę `dist\MiniScreenShot_v1.1.5_windows.zip`. Skrypt przygotowuje środowisko i instaluje zależności z przypiętymi wersjami. Biblioteki nie są pakowane przez UPX.

Głównym plikiem aplikacji jest `app_advanced.py`. Szczegółowa obsługa, ograniczenia przewijania i polecenia sprawdzające są opisane w [README_advanced.md](README_advanced.md).

## Licencja

Autor udziela użytkownikowi bezpłatnej, niewyłącznej licencji na korzystanie z programu w celach prywatnych i komercyjnych. Zabrania się modyfikowania, dekompilacji, inżynierii wstecznej kodu programu oraz jego sprzedaży lub czerpania bezpośrednich zysków z jego dystrybucji bez zgody autora.
