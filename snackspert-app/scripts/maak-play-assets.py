#!/usr/bin/env python3
"""
Zet schermafbeeldingen om naar iets dat de Google Play Console accepteert, en
schrijf de winkelteksten weg.

Google heeft een eis die Apple niet heeft: de langste zijde van een
schermafbeelding mag niet meer dan twee keer de kortste zijn. Een moderne
telefoon is langer dan dat (1179x2556 is 2,17 keer), dus zo'n bestand wordt
geweigerd. We zetten er daarom randen naast in de merkkleur tot de verhouding
klopt — bijsnijden zou de bovenkant of de tabbalk afhakken.

Gebruik: python3 scripts/maak-play-assets.py bestand1.png bestand2.png ...
"""

import re
import sys
from pathlib import Path
from PIL import Image

HIER = Path(__file__).resolve().parent.parent
UIT = HIER / 'winkel-assets' / 'screenshots-play'

DONKER = (26, 21, 18)   # #1A1512, dezelfde achtergrond als het app-icoon
MAX_VERHOUDING = 2.0


def pas_in(bron: Path, doel: Path) -> tuple[int, int]:
    im = Image.open(bron).convert('RGB')

    # Zo breed maken dat de langste zijde hooguit twee keer de kortste is.
    nodig = max(im.width, round(im.height / MAX_VERHOUDING))
    if nodig <= im.width:
        im.save(doel, 'PNG')
        return im.size

    doek = Image.new('RGB', (nodig, im.height), DONKER)
    doek.paste(im, ((nodig - im.width) // 2, 0))
    doek.save(doel, 'PNG')
    return doek.size


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
        # Een nummer dat er al voor staat niet nog eens toevoegen.
        kern = re.sub(r'^\d+-', '', bron.stem)
        naam = f'{nummer}-{kern}.png'
        voor = Image.open(bron).size
        na = pas_in(bron, UIT / naam)
        print(
            f'  {bron.name:18} {voor[0]}x{voor[1]} ({voor[1]/voor[0]:.2f}x)'
            f'  →  {naam}  {na[0]}x{na[1]} ({na[1]/na[0]:.2f}x)'
        )

    print(f'\nKlaar: {UIT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
