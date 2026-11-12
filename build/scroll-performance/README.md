# Pomiary przewijania

Skrypt `build/benchmark_scroll.py` mierzy aktualny silnik i równocześnie uruchamia test poprawności przechwytywania. Wymaga dostępnego pulpitu Windows; pomiary okna i przeglądarki uruchamiaj kolejno.

```bat
python build/benchmark_scroll.py --label current-native
python build/benchmark_scroll.py --label current-browser --browser
python -m unittest test_capture_scaling test_scroll_large -v
```

Raporty JSON i obrazy powstają lokalnie w tym katalogu i są pomijane przez Git. Test przeglądarki używa lokalnej strony i oddzielnego profilu Firefoksa.

Automatyczne skalowanie jest sprawdzane na źródle 2736 × 26 000 px (71,136 MP). Wynik ma 1539 × 14 625 px (22,508 MP), czyli o 68,36% mniej pikseli, z zachowaniem całej wysokości dokumentu i zapisem jednego PNG. Testy mniejszych obrazów sprawdzają również zachowanie oryginalnych pikseli, pion, poziom i siatkę.

Czas raportu dużej strony obejmuje przechwycenie i zapis. Czasy nie gwarantują takiej samej wydajności każdej strony ani komputera. Przy porównywaniu wyników używaj tych samych dokumentów i ustawień, bez jednoczesnego uruchamiania innych testów obciążających komputer.

## Pomiary optymalizacji 1.1.11

Kontrolne profilowanie tego samego testu `test_scroll_large` na Pythonie 3.15 i Pillow 13.0.0, przed i po optymalizacji, dało:

| Pomiar | Przed optymalizacją | Po optymalizacji |
| --- | ---: | ---: |
| Czas `ScrollingCapture.capture()` | 11,87 s | 7,36 s |
| Liczba fragmentów | 40 | 31 |
| Kompletna zawartość | tak | tak |

To około 38% krótszy czas przechwytywania w tym przypadku. Pomiar obejmuje dopasowanie i składanie obrazu, bez końcowego zapisu PNG; oba przebiegi używały `cProfile`. Test nadal porównuje fragmenty z całej wysokości źródła i sprawdza końcową rozdzielczość.

Optymalizacja zwiększa skalibrowany krok w dużych obszarach, zachowując ostrożniejszy krok małych paneli, współdzieli wynik porównania pikseli między analizami i szybciej rozpoznaje identyczne klatki. Nie skraca limitu oczekiwania na opóźnione renderowanie CRM. Testy obejmują również powtarzalne tabele, animowane reklamy, banery, zmianę szybkości przewijania oraz brak pominiętych lub powielonych pikseli.
