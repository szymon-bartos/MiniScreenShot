# Ikona MiniScreenShot

Niebiesko-turkusowe narożniki kadru, góry, słońce i jasny kursor, na podstawie grafiki przesłanej przez użytkownika. Usunięto ciemne tło i płytkę pod symbolem; puste przestrzenie mają rzeczywistą przezroczystość alfa.

- [capture-frame.png](capture-frame.png): aktualne logo PNG z przezroczystością.
- [capture-frame.ico](capture-frame.ico): ikona Windows w rozmiarach 16, 20, 24, 32, 40, 48, 64, 96, 128 i 256 px.
- `../build/prepare_icon.py`: konwersja PNG do ICO, bez retuszu.

Tło usunięto wbudowanym narzędziem **imagegen**, w trybie edycji przesłanego obrazu. Wspólne zasoby są wykorzystywane w EXE, paskach tytułu i zadań oraz nagłówkach głównego okna i podglądu. Starsze grafiki `monitor-grab`, `monitor-hand` i `monitor-paw` zachowano jako poprzednie warianty.

## Prompt usunięcia tła

Use case: background-extraction. Asset type: Windows screenshot application icon, transparent PNG. Input image 1 is the EDIT TARGET supplied by the user, not merely a style reference. Remove the dark background and dark rounded-square backing tile completely, including the exterior shadow, so only the original colorful screenshot emblem remains on genuine alpha transparency. Preserve faithfully the four cyan/blue capture corner brackets, the overlapping blue mountain shapes, the light blue circular sun, and the white/light-blue mouse pointer, their positions, silhouettes, colors, gradients, glossy bevels and relative sizes. Preserve any thin dark edge belonging to the pointer itself; remove the dark navy empty areas behind and between all shapes. Center the complete original emblem on a square transparent canvas with modest even transparent margins and no clipping. Change only background transparency; do not redesign the graphic, add text, add objects, recolor, or add another enclosing tile. Output one high quality clean cutout with smooth alpha edges, not a checkerboard painted into the image.

## Prompt oczyszczenia krawędzi

Use case: background-extraction. Edit target: attached transparent screenshot icon cutout. Clean up ONLY the cutout alpha boundary and empty background: remove every isolated cyan/blue/white speck, fringe, hole-edge noise, accidental pixel, and diffuse halo outside the solid icon shapes. The empty regions between the four corner brackets and the central picture/sun/pointer must be perfectly alpha=0, as must the exterior margins. Give all intended shapes precise, smooth antialiased silhouettes. Keep the four cyan/blue capture corner brackets, blue mountains, circular pale-blue sun, and large white/light-blue pointer with its thin dark outline unchanged in color, shape, proportions, position, and gloss. Keep genuine transparency, square canvas, modest clean transparent margins. Do not redesign, add text, add any new backdrop, or retain the dark rounded square tile. One clean production-ready application icon.
