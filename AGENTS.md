# Zasady projektu MiniScreenShot

- Każda kolejna zmiana dostarczana użytkownikowi musi otrzymać nowy numer wersji. Nie publikuj zmienionego programu pod numerem poprzedniego wydania.
- Aktualizuj `APP_VERSION` w `app_advanced.py`, nowy plik specyfikacji PyInstaller, `build_advanced_exe.bat`, `build/smoke_exe.py` i dokumentację. Nazwa EXE oraz tag wydania muszą odpowiadać wersji aplikacji.
- Bieżąca wersja to 1.1.7; następną poprawkę wydaj jako 1.1.8 lub wyższą.
- Przed wysłaniem zmian na GitHub usuń zbędne pliki robocze i wersje starsze niż cztery poprzednie. Zachowuj bieżącą wersję oraz cztery wcześniejsze, porównując numery wersji numerycznie. Aktualnie są to 1.1.7, 1.1.6, 1.1.5, 1.1.4 i 1.1.3. Zachowuj zasoby wymagane przez pozostawione specyfikacje oraz zrzuty użytkownika; nie przepisuj historii Git.
- Zachowuj dokładny tekst autora i licencji z `app_information.py` oraz `LICENSE.txt`, chyba że użytkownik poprosi o zmianę.
- Nie dodawaj do repozytorium zrzutów użytkownika, logów, profili przeglądarek, plików roboczych ani danych logowania. Gotowe EXE publikuj jako załączniki wydań GitHub.
- Dokumentacja aplikacji ma opisywać jej funkcje, obsługę, budowanie i testowanie. Nie publikuj w niej promptów ani zapisów pracy z asystentem.
- Od 1.1.5 publikuj pełną paczkę ZIP z EXE i bibliotekami (PyInstaller onedir, bez UPX); sam EXE wymaga katalogu `_internal`. Nie przywracaj samorozpakowującego trybu onefile bez wyjaśnienia zgłoszenia Defendera `Behavior:Win32/DefenseEvasion.A!ml`. Nie wyłączaj ochrony ani nie dodawaj wyjątków. Lokalny skan nie oznacza rozstrzygnięcia przez Microsoft.
- Dane robocze przechowuj w `C:\MiniScreenShot\cache`, a przy braku dostępu w `%LOCALAPPDATA%\MiniScreenShot\cache`. Sprzątaj wyłącznie oznaczone katalogi własnych nieaktywnych sesji. Zachowuj zrzuty użytkownika.
