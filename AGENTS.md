# Zasady projektu MiniScreenShot

- Każda kolejna zmiana dostarczana użytkownikowi musi otrzymać nowy numer wersji. Nie publikuj zmienionego programu pod numerem poprzedniego wydania.
- Aktualizuj `APP_VERSION` w `app_advanced.py`, nowy plik specyfikacji PyInstaller, `build_advanced_exe.bat`, `build/smoke_exe.py` i dokumentację. Nazwa EXE oraz tag wydania muszą odpowiadać wersji aplikacji.
- Bieżąca wersja to 1.1.3; następną poprawkę wydaj jako 1.1.4 lub wyższą.
- Przed wysłaniem zmian na GitHub usuń zbędne pliki robocze i wersje starsze niż cztery poprzednie. Zachowuj bieżącą wersję oraz cztery wcześniejsze, porównując numery wersji numerycznie. Aktualnie są to 1.1.3, 1.1.2, 1.1.1, 1.0.14 i 1.0.13. Zachowuj zasoby wymagane przez pozostawione specyfikacje oraz zrzuty użytkownika; nie przepisuj historii Git.
- Zachowuj dokładny tekst autora i licencji z `app_information.py` oraz `LICENSE.txt`, chyba że użytkownik poprosi o zmianę.
- Nie dodawaj do repozytorium zrzutów użytkownika, logów, profili przeglądarek, plików roboczych ani danych logowania. Gotowe EXE publikuj jako załączniki wydań GitHub.
