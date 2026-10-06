#!/usr/bin/env python3
"""
Zet schermafbeeldingen om naar een formaat dat App Store Connect accepteert.

Apple accepteert maar een handvol exacte afmetingen, en die van je eigen toestel
zit daar meestal niet bij — vandaar "File dimensions are invalid". Dit script
schaalt je schermafbeelding op tot hij het doelformaat volledig vult en snijdt
dan het laatste randje weg, zodat er niets vervormt en er geen balken omheen
komen.

Gebruik:
    python3 scripts/maak-screenshots.py schermafbeelding1.png schermafbeelding2.png ...

De bestanden komen in winkel-assets/screenshots-ios/, genummerd in de volgorde
waarin je ze meegeeft — en dat is ook de volgorde waarin ze in de App Store
komen te staan.
"""

import sys
from pathlib import Path
from PIL import Image

# Apple accepteert voor een iPhone-schermafbeelding deze afmetingen. Welke het
# uploadvak precies wil verschilt, dus we maken ze allebei; je uploadt de map
# die het accepteert.
FORMATEN = {
    '1320x2868': (1320, 2868),   # 6,9 inch
    '1290x2796': (1290, 2796),   # 6,7 / 6,9 inch
}

BASIS = Path(__file__).resolve().parent.parent / 'winkel-assets' / 'screenshots-ios'


def pas_in(bron: Path, doel: Path, maat: tuple[int, int]) -> None:
    im = Image.open(bron).convert('RGB')

    # Opschalen tot hij beide zijden dekt, daarna centreren en bijsnijden.
    schaal = max(maat[0] / im.width, maat[1] / im.height)
    nieuw = (round(im.width * schaal), round(im.height * schaal))
    im = im.resize(nieuw, Image.LANCZOS)

    links = (nieuw[0] - maat[0]) // 2
    boven = (nieuw[1] - maat[1]) // 2
    im.crop((links, boven, links + maat[0], boven + maat[1])).save(doel, 'PNG')


def main(argumenten: list[str]) -> int:
    if not argumenten:
        print(__doc__)
        return 1

    for label, maat in FORMATEN.items():
        uit = BASIS / label
        uit.mkdir(parents=True, exist_ok=True)
        print(f'{label}:')
        for nummer, pad in enumerate(argumenten, start=1):
            bron = Path(pad)
            if not bron.is_file():
                print(f'  overgeslagen (bestaat niet): {bron}')
                continue
            naam = f'{nummer}-{bron.stem}.png'
            pas_in(bron, uit / naam, maat)
            print(f'  {bron.name:18} →  {naam}')
        print()

    print(f'Klaar: {BASIS}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
