#!/usr/bin/env python3
"""Genereer de winkelbestanden voor de Play Console uit het bestaande logo."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ASSETS = Path('/home/user/snackspert/snackspert-app/assets')
UIT = Path('/home/user/snackspert/snackspert-app/winkel-assets')
UIT.mkdir(exist_ok=True)

DONKER = (26, 21, 18)       # #1A1512, de achtergrond van je app-icoon
GOUD = (237, 170, 45)       # #EDAA2D, je accentkleur

# ── 1. App-icoon 512x512 ────────────────────────────────────────
icoon = Image.open(ASSETS / 'icon.png').convert('RGB')
icoon.resize((512, 512), Image.LANCZOS).save(UIT / 'play-icoon-512.png')
print('play-icoon-512.png            512x512')

# ── 2. Feature graphic 1024x500 (de "header") ───────────────────
B, H = 1024, 500
doek = Image.new('RGB', (B, H), DONKER)

woordmerk = Image.open(ASSETS / 'SNACKSPERT_LOGO_SB_PIXEL.png').convert('RGBA')
breedte = int(B * 0.62)
schaal = breedte / woordmerk.width
woordmerk = woordmerk.resize((breedte, int(woordmerk.height * schaal)), Image.LANCZOS)

tagline = 'ALLE SNACKS, EERLIJK GETEST'
font = ImageFont.truetype(
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 26
)
teken = ImageDraw.Draw(doek)
# Letterafstand met de hand, want PIL kan dat niet zelf.
spatie = 4
tekstbreedte = sum(teken.textlength(c, font=font) + spatie for c in tagline) - spatie

# Logo en tagline als één blok verticaal centreren.
tussenruimte = 34
blok = woordmerk.height + tussenruimte + 30
top = (H - blok) // 2

doek.paste(woordmerk, ((B - woordmerk.width) // 2, top), woordmerk)

x = (B - tekstbreedte) / 2
y = top + woordmerk.height + tussenruimte
for c in tagline:
    teken.text((x, y), c, font=font, fill=GOUD)
    x += teken.textlength(c, font=font) + spatie

doek.save(UIT / 'play-header-1024x500.png')
print('play-header-1024x500.png     1024x500')
