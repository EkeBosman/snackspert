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

# iPhone 6,9 inch. Lever je deze aan, dan gebruikt Apple hem voor alle
# schermformaten en hoef je niets anders te maken.
DOEL = (1320, 2868)

UIT = Path(__file__).resolve().parent.parent / 'winkel-assets' / 'screenshots-ios'


def pas_in(bron: Path, doel: Path) -> None:
    im = Image.open(bron).convert('RGB')

    # Opschalen tot hij beide zijden dekt, daarna centreren en bijsnijden.
    schaal = max(DOEL[0] / im.width, DOEL[1] / im.height)
    nieuw = (round(im.width * schaal), round(im.height * schaal))
    im = im.resize(nieuw, Image.LANCZOS)

    links = (nieuw[0] - DOEL[0]) // 2
    boven = (nieuw[1] - DOEL[1]) // 2
    im = im.crop((links, boven, links + DOEL[0], boven + DOEL[1]))

    im.save(doel, 'PNG')


def main(argumenten: list[str]) -> int:
    if not argumenten:
        print(__doc__)
        return 1

    UIT.mkdir(parents=True, exist_ok=True)

    for nummer, pad in enumerate(argumenten, start=1):
        bron = Path(pad)
        if not bron.is_file():
            print(f'  overgeslagen (bestaat niet): {bron}')
            continue
        naam = f'{nummer}-{bron.stem}.png'
        pas_in(bron, UIT / naam)
        oorspronkelijk = Image.open(bron).size
        print(f'  {bron.name:18} {oorspronkelijk[0]}x{oorspronkelijk[1]}  →  {naam}  {DOEL[0]}x{DOEL[1]}')

    print(f'\nKlaar: {UIT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
