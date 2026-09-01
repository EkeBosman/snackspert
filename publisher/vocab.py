"""Vaste keuzelijsten en huisstijlwoorden.

Dit is een lokale kopie voor snelle offline controle. De site blijft leidend: het
endpoint toetst opnieuw tegen de echte ACF-keuzelijst, en `doctor` laat zien of
deze lijst nog klopt met wat er op de site staat.
"""

# ACF select-veld "category" en "main_category" delen deze lijst.
CATEGORIEEN = [
    "5-sterren",
    "aziatisch",
    "bakker",
    "borrel",
    "broodjes",
    "frietpatat",
    "grieks",
    "hamburger",
    "hotdogs",
    "italiaans",
    "kroket",
    "mexicaans",
    "midden-oosters",
    "pizza",
    "shoarma-doner",
    "snackbar",
    "spaans",
    "spareribs",
    "wraps",
    "overig",
]

# ACF select-veld "diet" (optioneel, meervoudig).
DIETEN = ["Vega", "Vegan"]

# Tekens die wel in een review mogen staan; al het andere symboolwerk vangt de
# emoji-controle af. De sterren horen bij de beoordeling en zijn dus toegestaan.
TOEGESTANE_SYMBOLEN = {"⭐", "★", "½", "️"}

# Snackspert is hartig. Deze woorden zijn een signaal dat er zoete content
# insluipt; het blijft een waarschuwing, want "ijssalon met broodje kroket" kan.
ZOETE_WOORDEN = [
    "brownie",
    "cheesecake",
    "chocolade",
    "chocola",
    "cupcake",
    "dessert",
    "donut",
    "gebak",
    "ijs",
    "ijsje",
    "koek",
    "koekje",
    "milkshake",
    "nagerecht",
    "oliebol",
    "pannenkoek",
    "poffertjes",
    "slagroom",
    "snoep",
    "stroopwafel",
    "suikerspin",
    "taart",
    "toetje",
    "wafel",
]
