# MiniScreenShot v1.1.8

Przenośny program do zrzutów ekranu na Windows. Rozpakuj pełną paczkę ZIP i uruchom `MiniScreenShot_v1.1.8.exe`, zachowując sąsiedni katalog `_internal`. Lokalny wynik budowania to `dist\MiniScreenShot_v1.1.8\MiniScreenShot_v1.1.8.exe`. Python nie jest wymagany do korzystania z gotowego programu.

Aplikacja obsługuje przechwytywanie ekranu i przewijanej zawartości, przycinanie oraz oznaczanie obrazu ołówkiem i półprzezroczystym mazakiem. Duże zrzuty z przewijaniem są proporcjonalnie zmniejszane do około 24 megapikseli lub mniej. Mniejsze zrzuty zachowują pełną rozdzielczość.

Przykład: strona 2736 × 26 000 px (71,1 MP) daje obraz 1539 × 14 625 px (22,5 MP), czyli około 68% mniej pikseli. Cała zawartość trafia do jednego PNG. Przy dużym powiększeniu podgląd renderuje tylko widoczną część obrazu. Jeśli strona przestanie się przewijać, zmieni treść lub osiągnie limit kroków, program zachowuje uzyskany fragment i wyraźnie oznacza podgląd jako „Zrzut częściowy”. [Testy i pomiary](build/scroll-performance/README.md).

Przechwytywanie i dopasowywanie fragmentów nadal odbywa się w jednym przejściu. Każdy pobrany fragment jest od razu zachowywany, a wielkość kroku dostosowuje się podczas pracy. Po dotarciu do końca program składa zapisane fragmenty bez ponownego przewijania strony. Dopasowywanie korzysta z klatek w oryginalnej rozdzielczości; zmniejszane są fragmenty przechowywane do składania i końcowy obraz.

Górny pasek aplikacji jest zachowywany jeden raz nad połączoną zawartością. Nieruchome boczne elementy i dolny pasek również są umieszczane raz. Limit około 24 MP obejmuje cały wynik, łącznie z paskami. Wąski panel pod punktem przewijania jest analizowany osobno od nieruchomego otoczenia. Pierwsze kroki są małe, aby ustalić przesunięcie; przeglądarka dostaje dodatkowy czas tylko wtedy, gdy jeszcze nie pokazała ruchu. Jeśli żaden fragment się nie przesunął, podgląd informuje „Widoczny obszar”, zamiast sugerować pełny zrzut.

W powtarzalnych tabelach ERP nieruchoma siatka i jednakowe etykiety nie przesłaniają zmiany rekordów: dopasowanie uwzględnia zmieniające się fragmenty wierszy. Panel nie musi zajmować środka okna w kierunku przewijania. Zmiana klatki bez wspólnego fragmentu podczas szukania początku listy nie jest traktowana jako osiągnięcie jej granicy. Oczekiwanie na koniec renderowania również analizuje przewijany fragment, aby drobny tekst nie został uznany za zakończoną animację.

## Microsoft Excel

Wybierz okno desktopowego Excela i kierunki przewijania. Program łączy się z modelem obiektowym wybranego okna przez [mechanizm dostępności Office](https://learn.microsoft.com/en-us/windows/win32/api/oleacc/nf-oleacc-accessibleobjectfromwindow). Odczytuje granice wartości w aktywnym arkuszu za pomocą [Range.Find](https://learn.microsoft.com/en-us/office/vba/api/excel.range.find), po czym przewija wyłącznie do ostatniego wiersza lub kolumny danych. Nie otwiera innych plików ani nie zapisuje zmian w skoroszycie. Puste sformatowane komórki i formuły wyświetlające pusty tekst nie wydłużają zrzutu; puste przerwy między danymi pozostają w obrazie. Wstążka jest zachowywana raz.

Przed przechwytywaniem zakończ edycję komórki i zamknij okna dialogowe Excela. Zmiana aktywnego arkusza lub przełączenie do innej aplikacji przerywa zrzut. Excel w przeglądarce i inne programy arkuszowe korzystają z ogólnego mechanizmu obrazu; opisane granice danych dotyczą desktopowego Microsoft Excel.

Przewijanie porównuje podobieństwo fragmentów zamiast wymagać identycznych pikseli, toleruje drobne zmiany wyglądu i mierzy rzeczywiste przesunięcie podczas składania. Doładowanie zawartości lub zmiana prędkości przewijania nie powoduje automatycznego odrzucenia zrzutu. Jeśli ponowne pobranie klatki nie daje pewnego dopasowania, ale obraz nadal pasuje do wcześniejszego przesunięcia, program dopuszcza niewielką zakładkę. Informuje wtedy o tym w panelu postępu i statusie końcowym.

Podczas pracy pojawia się niewielki panel z animacją, bieżącym etapem i czasem. Nie przejmuje fokusu ani kółka myszy. Windows wyklucza panel z przechwytywania; gdy ta funkcja jest niedostępna, program ukrywa go na czas pobierania klatki. Esc anuluje przechwytywanie.

## Główne okno

- Karty wyboru trybu: cały ekran, okno aplikacji lub wybrany obszar.
- Lista **Język / Language** u góry: **Polski** i **English**, z natychmiastową zmianą oraz zapamiętaniem wyboru na kolejne uruchomienie.
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

Zmiana języka aktualizuje również otwarte podglądy, kolory, grubości narzędzi, podpowiedzi przycinania i okno informacji. Zachowuje obraz, powiększenie, zaznaczenie przycinania i historię cofania. Nazwy plików, tytuły zewnętrznych okien oraz tekst na obrazie nie są tłumaczone. Angielskie okno informacji pokazuje tłumaczenie licencji i jej oryginalny polski tekst.

## Wykonywanie zrzutów

Program obsługuje cały ekran, wybrane okno, zaznaczony wycinek oraz zrzuty okna z przewijaniem. Domyślny folder zapisów to `C:\Screenshots`; można wybrać inny w głównym oknie.

Program znajduje początek zawartości, a następnie podczas jednego przewijania pobiera kolejne fragmenty i mierzy ich przesunięcie. Kończy po osiągnięciu aktualnego końca strony, także po doładowaniu kolejnej zawartości. Poziom rozszerza szerokość obrazu, pion jego wysokość; oba kierunki tworzą siatkę. Stałe paski otaczające przewijaną zawartość nie są powielane. Po ukończeniu strona pozostaje na końcu; w siatce program wraca do lewej krawędzi między wierszami.

Nie zmieniaj aktywnego okna, rozmiaru ani powiększenia zawartości podczas przechwytywania. Esc anuluje zrzut. Drobne różnice obrazu mogą skutkować niewielką zakładką. Limit 240 kroków na kierunek i kontrola wolnego miejsca chronią przed stronami przewijającymi się bez końca; ich osiągnięcie daje zrzut częściowy z opisem przyczyny. Pliki robocze są usuwane po zamknięciu podglądu. Ostateczny PNG zapisujesz przyciskiem „Zapisz”.

Zdarzenia przewijania trafiają do zawartości wybranego okna, aby pasek adresu lub inne pole z fokusem nie przejmowało kółka.

## Uruchomienie kodu i budowanie EXE

1. Zainstaluj Python 3.11+ z obsługą Tkinter i zaznacz „Add Python to PATH”.
2. Uruchom `start_app.bat`, aby uruchomić program z kodu.
3. Uruchom `build_advanced_exe.bat`, aby zbudować `dist\MiniScreenShot_v1.1.8\MiniScreenShot_v1.1.8.exe` i paczkę `dist\MiniScreenShot_v1.1.8_windows.zip`.

Budowanie korzysta z `MiniScreenShot_v1.1.8.spec` w trybie folderowym, bez UPX. Zasoby Tcl/Tk dostarczane w archiwach ZIP z Pythonem 3.15 są przygotowywane podczas budowania i dołączane do paczki. Przy przenoszeniu programu zachowaj cały katalog `_internal` obok EXE.

## Cache i diagnostyka

Pliki robocze są przechowywane w `C:\MiniScreenShot\cache`, w osobnym folderze sesji dla każdej uruchomionej kopii. Jeśli zapis na C: nie jest dozwolony, aplikacja używa `%LOCALAPPDATA%\MiniScreenShot\cache` i nie prosi o uprawnienia administratora. Cache nie zawiera rozpakowywanych przy starcie bibliotek EXE: znajdują się one w `_internal` obok programu.

Limit cache wynosi 512 MB na sesję, z dodatkową rezerwą 256 MB wolnego miejsca na dysku. Fragmenty pojedynczego zrzutu mogą zajmować najwyżej 384 MB. Po osiągnięciu limitu program zachowuje uzyskany fragment jako zrzut częściowy. Zamykanie podglądu zwalnia jego pliki; zamykanie programu usuwa pozostałą sesję. Po awarii kolejny start sprząta wyłącznie oznaczone, nieaktywne sesje MiniScreenShot. Blokada systemowa chroni cache innych uruchomionych kopii. Zapisane PNG użytkownika pozostają na dysku.

`capture_debug.log` znajduje się w `C:\MiniScreenShot\logs` lub w folderze `logs` obok zastępczego cache. Rotacja zachowuje bieżący plik i dwie kopie, po około 512 KB. Odczyt jest dostępny pod przyciskiem `Diagnostyka`.

Preferencja języka jest zapisywana w małym pliku `C:\MiniScreenShot\settings.json`, a przy braku dostępu w `%LOCALAPPDATA%\MiniScreenShot\settings.json`. Jest oddzielona od sprzątanego cache. Brak lub uszkodzenie ustawień przywraca język polski; błąd zapisu nie blokuje zmiany języka w bieżącej sesji. Techniczne wpisy w historycznych logach zachowują oryginalną treść.

Wersja 1.1.4 otrzymała zgłoszenie Defendera `Behavior:Win32/DefenseEvasion.A!ml` podczas uruchamiania. W 1.1.5 zastosowano pakiet folderowy bez UPX i samorozpakowania przy starcie. Przyczyna zgłoszenia nie została potwierdzona przez Microsoft. Nie traktuj lokalnego skanu jako gwarancji ani nie dodawaj wyjątków antywirusa. Szczegóły i odnośnik do analizy Microsoft znajdują się w [README.md](README.md#status-zabezpieczeń).

## Sprawdzenie zmian

Po zainstalowaniu zależności uruchom:

```bat
python -m unittest test_app_storage test_preview_layout test_preview_annotations test_image_annotations test_capture_targeting test_window_catalog test_scroll_capture test_capture_scaling test_snapshot_timing test_capture_focus -v
```

Testy języków: `python -m unittest test_localization -v`. Sprawdzają kompletność parametrów tłumaczeń i komunikatów błędów, zapis ustawień, ponowne uruchomienie po wyborze angielskiego, zmianę języka w edytorze bez utraty oznaczeń lub przycięcia, wybór okna oraz oryginał i tłumaczenie licencji. Preferencje tych testów trafiają do własnego katalogu tymczasowego, bez zmiany ustawień użytkownika.

Testy cache sprawdzają limit miejsca, awaryjny katalog, usuwanie pozostałości po awarii, zachowanie aktywnych sesji i plików bez oznaczenia oraz zwalnianie plików po złożeniu zrzutu i zamknięciu obrazu. Testy interfejsu otwierają okna na pulpicie Windows i sprawdzają układ, dopasowanie obrazu, przycinanie, zapis, systemowe przyciski okna oraz przewijanie strzałkami i touchpadem w obu osiach. Test touchpada sprawdza również natywne komunikaty `WM_MOUSEWHEEL` i `WM_MOUSEHWHEEL` z niewielkimi przesunięciami; sposób kodowania precyzyjnych zdarzeń wynika z [implementacji Tk dla Windows](https://github.com/tcltk/tk/blob/core-9-0-branch/win/tkWinX.c). Podglądy z obrazem testowym zapisują się w `build\preview-review`.

Testy rysowania sprawdzają krycie ołówka, czytelność tekstu pod mazakiem i brak dodatkowego przyciemniania przy wielokrotnym przejechaniu tego samego miejsca jednym ruchem. Obejmują cofanie, zapis i kopiowanie oznaczeń, powiększenie, przewijanie, przycięcie, układ wąskiego okna i rysowanie na dużym obrazie mapowanym bez tworzenia pełnej kopii w pamięci. Sprawdzanie schowka używa atrap i nie zmienia zawartości schowka użytkownika.

Test rzeczywistego przechwytywania Windows: `python -m unittest test_scroll_live -v`. Wybiera okno z syntetyczną zawartością w głównym panelu i uruchamia zrzut jego przyciskiem, także przy otwartym wcześniejszym podglądzie. Sprawdza zwykły zrzut oraz przewijanie w obu kierunkach, porównując wynik z oryginałem piksel po pikselu. Porównuje również bezpośredni odczyt obszaru z Pillow i sprawdza zwalnianie zasobów GDI.

Test Firefoksa: `python -m unittest test_scroll_browser -v`. Otwiera lokalne strony w oddzielnym profilu w `build\browser-review`, sprawdza pełny zrzut przy płynnym przewijaniu, wąski panel CRM w nieruchomym interfejsie oraz brak loadera na obrazie. Nie korzysta z prywatnego profilu użytkownika.

Test Chrome: `python -m unittest test_scroll_chrome -v`. Używa osobnego profilu w `build\chrome-review` i syntetycznej tabeli 48 leadów, z powtarzalną siatką oraz zmieniającymi się identyfikatorami. Lista rysuje wyłącznie widoczne rekordy na canvasie. Test porównuje wszystkie piksele połączonej listy z oryginałem, także przy opóźnieniu renderowania 450 ms i rozpoczęciu od środka listy. Nie korzysta z profilu ani danych ERP użytkownika.

Test Excela: `python -m unittest test_excel_scroll -v`. Tworzy osobną instancję i testowy skoroszyt: 85 wierszy z pustą przerwą, formatowanie do wiersza 40 000, inny arkusz z danymi do wiersza 5000 oraz tabelę 30 kolumn. Sprawdza koniec na danych aktywnego arkusza i zachowanie wstążki. Zamyka wyłącznie własny skoroszyt bez zapisu.

Test dużej strony: `python -m unittest test_scroll_large -v`. Sprawdza proporcjonalne zmniejszenie źródłowych 71,1 MP do 22,5 MP, fragmenty z całej wysokości strony, brak drugiego przebiegu i zapis jednego PNG. Wymaga kilkuset MB wolnego miejsca na pliki robocze. `test_capture_scaling` sprawdza również zmianę skali podczas pracy, brak pustych pasów na łączeniach, pion, poziom i siatkę oraz zachowanie oryginalnych pikseli małych zrzutów.

Panel korzysta z Windows [SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity) i pokazywania okna bez aktywacji. Sprawdzenie loadera obejmuje również wariant bez obsługi wykluczania okien z przechwytywania.
