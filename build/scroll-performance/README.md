# Pomiary przewijania

Skrypt `build/benchmark_scroll.py` mierzy aktualny silnik i równocześnie uruchamia test poprawności przechwytywania. Wymaga dostępnego pulpitu Windows; pomiary okna i przeglądarki uruchamiaj kolejno.

```bat
python build/benchmark_scroll.py --label current-native
python build/benchmark_scroll.py --label current-browser --browser
python -m unittest test_capture_scaling test_scroll_large -v
```

Raporty JSON i obrazy powstają lokalnie w tym katalogu i są pomijane przez Git. Test przeglądarki używa lokalnej strony i oddzielnego profilu Firefoksa. Dane wcześniejszych, usuniętych wersji oraz kopie starego silnika nie są przechowywane w projekcie.

Automatyczne skalowanie jest sprawdzane na źródle 2736 × 26 000 px (71,136 MP). Wynik ma 1539 × 14 625 px (22,508 MP), czyli o 68,36% mniej pikseli, z zachowaniem całej wysokości dokumentu i zapisem jednego PNG. Testy mniejszych obrazów sprawdzają również zachowanie oryginalnych pikseli, pion, poziom i siatkę.

Czas raportu dużej strony obejmuje przechwycenie i zapis. Czasy nie gwarantują takiej samej wydajności każdej strony ani komputera. Przy porównywaniu wyników używaj tych samych dokumentów i ustawień, bez jednoczesnego uruchamiania innych testów obciążających komputer.
