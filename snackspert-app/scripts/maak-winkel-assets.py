#!/usr/bin/env python3
"""
Genereer de winkelbestanden voor App Store Connect en de Play Console uit het
bestaande logo, zodat ze allemaal dezelfde huisstijl hebben als het app-icoon.

Gebruik: python3 scripts/maak-winkel-assets.py
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
ASSETS = HIER / 'assets'
UIT = HIER / 'winkel-assets'
UIT.mkdir(exist_ok=True)

DONKER = (26, 21, 18)       # #1A1512, de achtergrond van je app-icoon
GOUD = (237, 170, 45)       # #EDAA2D, je accentkleur
TAGLINE = 'ALLE SNACKS, EERLIJK GETEST'
FONT = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'


def banner(breedte: int, hoogte: int, logo_deel: float = 0.62) -> Image.Image:
    """Woordmerk met tagline, gecentreerd op de merkachtergrond."""
    doek = Image.new('RGB', (breedte, hoogte), DONKER)

    woordmerk = Image.open(ASSETS / 'SNACKSPERT_LOGO_SB_PIXEL.png').convert('RGBA')
    doelbreedte = int(breedte * logo_deel)
    schaal = doelbreedte / woordmerk.width
    woordmerk = woordmerk.resize(
        (doelbreedte, int(woordmerk.height * schaal)), Image.LANCZOS
    )

    # Tekstgrootte meeschalen met het doek, zodat elk formaat er gelijk uitziet.
    tekengrootte = max(12, int(hoogte * 0.052))
    font = ImageFont.truetype(FONT, tekengrootte)
    teken = ImageDraw.Draw(doek)

    # Letterafstand met de hand: PIL kan dat niet zelf.
    spatie = max(2, int(tekengrootte * 0.16))
    tekstbreedte = sum(teken.textlength(c, font=font) + spatie for c in TAGLINE) - spatie

    tussenruimte = int(hoogte * 0.068)
    blok = woordmerk.height + tussenruimte + tekengrootte
    top = (hoogte - blok) // 2

    doek.paste(woordmerk, ((breedte - woordmerk.width) // 2, top), woordmerk)

    x = (breedte - tekstbreedte) / 2
    y = top + woordmerk.height + tussenruimte
    for c in TAGLINE:
        teken.text((x, y), c, font=font, fill=GOUD)
        x += teken.textlength(c, font=font) + spatie

    return doek


# ── App Store Connect ───────────────────────────────────────────
# De twee maten die App Store Connect noemt bij "Header".
for b, h in [(5244, 2950), (3840, 1646)]:
    naam = f'appstore-header-{b}x{h}.png'
    # Bij de brede, lage variant past het logo smaller, anders raakt het de rand.
    banner(b, h, logo_deel=0.62 if h / b > 0.4 else 0.46).save(UIT / naam)
    print(f'{naam:34} {b}x{h}')

# ── Play Console ────────────────────────────────────────────────
icoon = Image.open(ASSETS / 'icon.png').convert('RGB')
icoon.resize((512, 512), Image.LANCZOS).save(UIT / 'play-icoon-512.png')
print(f'{"play-icoon-512.png":34} 512x512')

banner(1024, 500).save(UIT / 'play-header-1024x500.png')
print(f'{"play-header-1024x500.png":34} 1024x500')
