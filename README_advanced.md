# MiniScreenShot v1.1.4

Przenośny program do zrzutów ekranu na Windows. Gotowy plik uruchomisz z `dist\MiniScreenShot_v1.1.4.exe`, bez instalowania Pythona.

Aplikacja obsługuje przechwytywanie ekranu i przewijanej zawartości, przycinanie oraz oznaczanie obrazu ołówkiem i półprzezroczystym mazakiem. Duże zrzuty z przewijaniem są proporcjonalnie zmniejszane do około 24 megapikseli lub mniej. Mniejsze zrzuty zachowują pełną rozdzielczość.

Przykład: strona 2736 × 26 000 px (71,1 MP) daje obraz 1539 × 14 625 px (22,5 MP), czyli około 68% mniej pikseli. Cała zawartość trafia do jednego PNG. Przy dużym powiększeniu podgląd renderuje tylko widoczną część obrazu. Jeśli strona przestanie się przewijać, zmieni treść lub osiągnie limit kroków, program zachowuje uzyskany fragment i wyraźnie oznacza podgląd jako „Zrzut częściowy”. [Testy i pomiary](build/scroll-performance/README.md).

Przechwytywanie i dopasowywanie fragmentów nadal odbywa się w jednym przejściu. Każdy pobrany fragment jest od razu zachowywany, a wielkość kroku dostosowuje się podczas pracy. Po dotarciu do końca program składa zapisane fragmenty bez ponownego przewijania strony. Dopasowywanie korzysta z klatek w oryginalnej rozdzielczości; zmniejszane są fragmenty przechowywane do składania i końcowy obraz.

Przewijanie porównuje podobieństwo fragmentów zamiast wymagać identycznych pikseli, toleruje drobne zmiany wyglądu i mierzy rzeczywiste przesunięcie podczas składania. Doładowanie zawartości lub zmiana prędkości przewijania nie powoduje automatycznego odrzucenia zrzutu. Jeśli ponowne pobranie klatki nie daje pewnego dopasowania, ale obraz nadal pasuje do wcześniejszego przesunięcia, program dopuszcza niewielką zakładkę. Informuje wtedy o tym w panelu postępu i statusie końcowym.

Podczas pracy pojawia się niewielki panel z animacją, bieżącym etapem i czasem. Nie przejmuje fokusu ani kółka myszy. Windows wyklucza panel z przechwytywania; gdy ta funkcja jest niedostępna, program ukrywa go na czas pobierania klatki. Esc anuluje przechwytywanie.

## Główne okno

- Karty wyboru trybu: cały ekran, okno aplikacji lub wybrany obszar.
- Zaokrąglone przyciski z podświetleniem i obsługą klawiatury.
- Przełączniki przewijania w pionie i poziomie, domyślnie wyłączone, aktywne w trybie okna aplikacji. Po ich włączeniu przycisk zmienia nazwę na „Zrób zrzut z przewijaniem”.
- Widoczny przycisk wykonania zrzutu. W małym oknie ustawienia można przewijać.
- Skalowanie odstępów i elementów sterujących zgodnie z ustawieniami Windows.
- W trybie „Okno aplikacji” lista okien znajduje się w głównym panelu. Najpierw pokazuje nazwę programu, potem plik, stronę lub tytuł okna.
- Wyszukiwanie po nazwie programu i tytule, odświeżanie z zachowaniem wyboru oraz zatwierdzanie wybranego okna przyciskiem zrzutu, Enterem lub dwuklikiem.
- Nazwy programów są odczytywane z procesu Windows; jeśli Windows nie udostępni tych danych, program korzysta z rozpoznanego tytułu lub oznacza okno jako „Aplikacja”.
- Przycisk `Informacje` obok `Diagnostyka` pokazuje po kliknięciu autora, wersję i warunki licencji. Treść licencji znajduje się również w [LICENSE.txt](LICENSE.txt), jest dołączana do EXE i kopiowana do katalogu `dist` podczas budowania.

## Podgląd po wykonaniu zrzutu

- Nowy podgląd otwiera się na wierzchu i otrzymuje fokus. Przełącznik „Na wierzchu” pozwala wyłączyć przypięcie nad innymi aplikacjami.
- Przyciski, suwak i kolory są zgodne z wyglądem głównego panelu.
- Okna programu są ukrywane podczas przechwytywania, aby nie zasłaniały zrzutu, i przywracane przed pokazaniem nowego podglądu.
- Systemowy pasek tytułu z minimalizacją, maksymalizacją, przywracaniem i zamykaniem okna.
- Elastyczny pasek narzędzi: przyciski przechodzą do kolejnych rzędów przy zwężaniu okna.
- Minimalna wysokość uwzględnia liczbę rzędów i skalowanie tekstu Windows, aby zostawić miejsce na obraz.
- Automatyczne dopasowanie całego obrazu do okna, także długich zrzutów z przewijaniem.
- Przyciski `Dopasuj` i `100%`, suwak, powiększanie przez `Ctrl + kółko myszy` oraz paski przewijania.
- Przewijanie obrazu strzałkami po kliknięciu w obraz; `Page Up` / `Page Down` przesuwają o większy fragment.
- Kółko lub dwa palce na touchpadzie przewijają w pionie. Gest poziomy lub `Shift + kółko` przesuwa w poziomie. Przewijanie zachowuje powiększenie i zaznaczenie przycinania.
- Ręcznie ustawione powiększenie zostaje zachowane przy zmianie rozmiaru okna.
- Przycinanie bezpośrednio w oknie podglądu. Kliknij `Przytnij` i przeciągnij na obrazie; zaznaczenie można przesuwać lub zmieniać uchwytami przy jego krawędziach.
- `Zatwierdź` lub Enter stosuje przycięcie, a `Anuluj` lub Esc zachowuje poprzedni obraz. Zaznaczenie uwzględnia powiększenie i przewijanie podglądu.
- `Ołówek` rysuje kryjącą kreskę; `Mazak` podświetla fragmenty, pozostawiając widoczny tekst. Wybierz narzędzie, kolor i jedną z trzech grubości, a następnie przeciągnij po obrazie. Kliknięcie bez przeciągania stawia kropkę.
- Ponowne kliknięcie aktywnego narzędzia lub Esc kończy rysowanie. Esc anuluje również jeszcze niezatwierdzoną kreskę. `Cofnij` / `Ctrl+Z` cofa oznaczenia. Przycinanie zachowuje oznaczenia na pozostawionym fragmencie i rozpoczyna nową historię cofania.
- Zapis PNG i kopiowanie obrazu do schowka.
- Informacja o automatycznym zmniejszeniu dużego zrzutu obok jego wymiarów.

Skróty w podglądzie: `Ctrl+S` — zapisz, `Ctrl+C` — kopiuj, `Ctrl+Z` — cofnij oznaczenie, `Ctrl+0` — dopasuj, `Ctrl+1` — 100%.

## Wykonywanie zrzutów

Program obsługuje cały ekran, wybrane okno, zaznaczony wycinek oraz zrzuty okna z przewijaniem. Domyślny folder zapisów to `C:\Screenshots`; można wybrać inny w głównym oknie.

Program znajduje początek zawartości, a następnie podczas jednego przewijania pobiera kolejne fragmenty i mierzy ich przesunięcie. Kończy po osiągnięciu aktualnego końca strony, także po doładowaniu kolejnej zawartości. Poziom rozszerza szerokość obrazu, pion jego wysokość; oba kierunki tworzą siatkę. Stałe paski otaczające przewijaną zawartość nie są powielane. Po ukończeniu strona pozostaje na końcu; w siatce program wraca do lewej krawędzi między wierszami.

Nie zmieniaj aktywnego okna, rozmiaru ani powiększenia zawartości podczas przechwytywania. Esc anuluje zrzut. Drobne różnice obrazu mogą skutkować niewielką zakładką. Limit 240 kroków na kierunek i kontrola wolnego miejsca chronią przed stronami przewijającymi się bez końca; ich osiągnięcie daje zrzut częściowy z opisem przyczyny. Pliki robocze są usuwane po zamknięciu podglądu. Ostateczny PNG zapisujesz przyciskiem „Zapisz”.

Zdarzenia przewijania trafiają do zawartości wybranego okna, aby pasek adresu lub inne pole z fokusem nie przejmowało kółka.

## Uruchomienie kodu i budowanie EXE

1. Zainstaluj Python 3.11+ z obsługą Tkinter i zaznacz „Add Python to PATH”.
2. Uruchom `start_app.bat`, aby uruchomić program z kodu.
3. Uruchom `build_advanced_exe.bat`, aby zbudować `dist\MiniScreenShot_v1.1.4.exe`.

Budowanie korzysta z `MiniScreenShot_v1.1.4.spec`. Zasoby Tcl/Tk dostarczane w archiwach ZIP z Pythonem 3.15 są rozpakowywane i dołączane do EXE. Program pozostaje jednym plikiem wykonywalnym.

## Sprawdzenie zmian

Po zainstalowaniu zależności uruchom:

```bat
python -m unittest test_preview_layout test_preview_annotations test_image_annotations test_capture_targeting test_window_catalog test_scroll_capture test_capture_scaling test_snapshot_timing test_capture_focus -v
```

Testy interfejsu otwierają okna na pulpicie Windows i sprawdzają układ, dopasowanie obrazu, przycinanie, zapis, systemowe przyciski okna oraz przewijanie strzałkami i touchpadem w obu osiach. Test touchpada sprawdza również natywne komunikaty `WM_MOUSEWHEEL` i `WM_MOUSEHWHEEL` z niewielkimi przesunięciami; sposób kodowania precyzyjnych zdarzeń wynika z [implementacji Tk dla Windows](https://github.com/tcltk/tk/blob/core-9-0-branch/win/tkWinX.c). Podglądy z obrazem testowym zapisują się w `build\preview-review`.

Testy rysowania sprawdzają krycie ołówka, czytelność tekstu pod mazakiem i brak dodatkowego przyciemniania przy wielokrotnym przejechaniu tego samego miejsca jednym ruchem. Obejmują cofanie, zapis i kopiowanie oznaczeń, powiększenie, przewijanie, przycięcie, układ wąskiego okna i rysowanie na dużym obrazie mapowanym bez tworzenia pełnej kopii w pamięci. Sprawdzanie schowka używa atrap i nie zmienia zawartości schowka użytkownika.

Test rzeczywistego przechwytywania Windows: `python -m unittest test_scroll_live -v`. Wybiera okno z syntetyczną zawartością w głównym panelu i uruchamia zrzut jego przyciskiem, także przy otwartym wcześniejszym podglądzie. Sprawdza zwykły zrzut oraz przewijanie w obu kierunkach, porównując wynik z oryginałem piksel po pikselu. Porównuje również bezpośredni odczyt obszaru z Pillow i sprawdza zwalnianie zasobów GDI.

Test Firefoksa: `python -m unittest test_scroll_browser -v`. Otwiera lokalną stronę w oddzielnym profilu w `build\browser-review`, sprawdza pełny zrzut przy płynnym przewijaniu oraz brak loadera na obrazie. Nie korzysta z prywatnego profilu użytkownika.

Test dużej strony: `python -m unittest test_scroll_large -v`. Sprawdza proporcjonalne zmniejszenie źródłowych 71,1 MP do 22,5 MP, fragmenty z całej wysokości strony, brak drugiego przebiegu i zapis jednego PNG. Wymaga kilkuset MB wolnego miejsca na pliki robocze. `test_capture_scaling` sprawdza również zmianę skali podczas pracy, brak pustych pasów na łączeniach, pion, poziom i siatkę oraz zachowanie oryginalnych pikseli małych zrzutów.

Panel korzysta z Windows [SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity) i pokazywania okna bez aktywacji. Sprawdzenie loadera obejmuje również wariant bez obsługi wykluczania okien z przechwytywania.
