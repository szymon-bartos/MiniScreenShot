# Pomiary przewijania

## 1.0.13: mniejsze zużycie zasobów przez duże zrzuty

Zrzuty z przewijaniem są automatycznie zmniejszane do maksymalnie około 24 MP. Skala maleje proporcjonalnie w krokach 75%, więc wynik może być mniejszy od progu. Kolejne fragmenty trafiają do pamięci lub plików już po zmniejszeniu; starsze mogą mieć inną rozdzielczość i są przeliczane do wspólnej skali przy składaniu. Dopasowywanie przesunięcia nadal korzysta z oryginalnych klatek. Zwykłe zrzuty poniżej progu zachowują swoje piksele.

| Pełna zawartość strony | Zapisany obraz | Liczba pikseli |
| --- | --- | ---: |
| 2736 × 26 000 px (71,136 MP) | 1539 × 14 625 px (22,508 MP) | o 68,36% mniej |

Raport: [duża strona ze skalowaniem](large-scaled.json). Test tworzy lokalnie `large-scaled.png` i sprawdza fragmenty z całej wysokości strony, poprawne proporcje, jeden przebieg i zapis do jednego PNG. Czas w raporcie obejmuje również zapis pliku; nie jest porównaniem wydajności z wcześniejszymi pomiarami. Podgląd pokazuje informację o zmniejszeniu i nie tworzy dodatkowej pełnej kopii obrazu. Przy zamykaniu podglądu zwalnia także ostatni zrzut przechowywany przez aplikację.

```bat
python -m unittest test_capture_scaling test_scroll_large -v
```

## 1.0.12: przechwytywanie w jednym przejściu

Silnik nie wykonuje osobnego przebiegu pomiarowego ani powrotu na początek po zrzucie pionowym. Podczas przewijania zapisuje klatki i ich zmierzone położenie. Niewielkie zestawy pozostają w pamięci (do 64 MB); większe korzystają z plików roboczych. Wynik powyżej progu pamięci jest obrazem RGBA opartym na pliku mapowanym, nadal zapisywanym jako jeden PNG w pełnej rozdzielczości.

| Scenariusz | 1.0.11 | 1.0.12 |
| --- | ---: | ---: |
| Firefox, łącznie obraz i strona HTML | 16,67 s | 11,00 s |
| Pobrania ustabilizowanych klatek w tym teście | 50 | 23 |

Raport: [Firefox 1.0.12](single-pass-browser.json). Lokalne strony obejmują dokładne porównanie wszystkich wierszy obrazu i listę ogłoszeń z fotografiami, tekstem, skalowaniem oraz zmianami jasności. Czas obejmuje przygotowanie początku, przechwycenie i złożenie, bez uruchamiania Firefoksa i podglądu.

Osobny historyczny test [dużej strony](large-single-pass.json) sprawdzał 2736 × 26 000 px (71,136 MP), zachowanie pikseli z całej wysokości i zapis do jednego PNG. Dokument testowy i wynik `large-single-pass.png` były generowane lokalnie. Ten test przekraczał dawny limit 60 MP i potwierdzał brak powtórnego przewijania; aktualny test korzysta z automatycznego skalowania opisanego wyżej.

Testy sprawdzają również zachowanie przechwyconej części przy błędzie dopasowania lub limicie kroków, animowaną reklamę przy końcu strony, odświeżający się pasek przeglądarki oraz podgląd i przycinanie dużego obrazu przy 100% powiększenia. Zrzut częściowy ma wyraźny nagłówek i opis przyczyny. Użytkownik zapisuje go przyciskiem „Zapisz”.

Firefox korzysta z natywnego wejścia kółka po sprawdzeniu aktywnego okna i okna pod kursorem. Jego [obsługa kółka](https://searchfox.org/firefox-main/source/widget/windows/WinMouseScrollHandler.cpp) odczytuje również pozycję natywnego komunikatu; samo wysłanie WM_MOUSEWHEEL z lParam nie zapewnia świeżej pozycji. Struktura wejścia jest zgodna z [MOUSEINPUT](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput). W pozostałych oknach zdarzenia nadal trafiają bezpośrednio do wybranej kontrolki.

Powtórzenie pomiaru:

```bat
python build/benchmark_scroll.py --label single-pass-browser --browser
python -m unittest test_scroll_large -v
```

## 1.0.10 → 1.0.11

Pomiary z 16.10.2026 na tym samym pulpicie Windows. Każdy przebieg wykonuje test poprawności rzeczywistego zrzutu. Czasy poniżej obejmują `ScrollingCapture.capture()`: wyszukanie granic, przechwycenie, złożenie obrazu i powrót na początek. Wykluczają uruchomienie aplikacji, przeglądarki oraz renderowanie podglądu. To wyniki konkretnych dokumentów testowych, a nie gwarantowane przyspieszenie każdej strony.

| Scenariusz | 1.0.10 | 1.0.11 | Przyspieszenie |
| --- | ---: | ---: | ---: |
| Okno Windows, siatka w pionie i poziomie | 94,45 s | 12,33 s | 7,66× |
| Firefox, łącznie obraz i strona HTML | 44,03 s | 16,67 s | 2,64× |

Zrzut okna jest porównywany z całym dokumentem 421 × 363 px piksel po pikselu. Test Firefoksa sprawdza wszystkie wiersze obrazu o wysokości 1373 px, potem pełną wysokość strony HTML z tekstem, zdjęciami, płynnym przewijaniem, skalowaniem 110% i zmianami jasności. Sprawdza znaczniki początku i końca oraz brak loadera na obrazie. HTML dopuszcza różnicę wysokości do 8 px; obraz i okno wymagają dokładnego dopasowania.

Analiza granic okna skróciła się z 15,37 do 3,08 s. W Firefoksie z 16,87 do 6,95 s. Liczba pobrań ustabilizowanych klatek okna spadła ze 161 do 70. Uwaga: czasy etapów w JSON zawierają się w sobie, więc nie należy ich sumować.

Raporty: [okno przed](baseline-native.json), [okno po](optimized-native.json), [Firefox przed](baseline-browser.json), [Firefox po](optimized-browser.json). Katalog `baseline` zawiera silnik i sterownik sprzed optymalizacji, aby umożliwić powtórzenie porównania.

Uruchamiaj po kolei na dostępnym pulpicie, bez przełączania do innych aplikacji:

```bat
python build/benchmark_scroll.py --label baseline-native --baseline
python build/benchmark_scroll.py --label optimized-native
python build/benchmark_scroll.py --label baseline-browser --browser --baseline
python build/benchmark_scroll.py --label optimized-browser --browser
```

Firefox uruchamia się na lokalnych plikach i w osobnym profilu testowym. Testy nie korzystają z prywatnego profilu użytkownika.
