# Zasady projektu MiniScreenShot

- Każda kolejna zmiana dostarczana użytkownikowi musi otrzymać nowy numer wersji. Nie publikuj zmienionego programu pod numerem poprzedniego wydania.
- Aktualizuj `APP_VERSION` w `app_advanced.py`, nowy plik specyfikacji PyInstaller, `build_advanced_exe.bat`, `build/smoke_exe.py` i dokumentację. Nazwa EXE oraz tag wydania muszą odpowiadać wersji aplikacji.
- Bieżąca wersja to 1.1.2; następną poprawkę wydaj jako 1.1.3 lub wyższą.
- Zachowuj dokładny tekst autora i licencji z `app_information.py` oraz `LICENSE.txt`, chyba że użytkownik poprosi o zmianę.
- Nie dodawaj do repozytorium zrzutów użytkownika, logów, profili przeglądarek, plików roboczych ani danych logowania. Gotowe EXE publikuj jako załączniki wydań GitHub.
