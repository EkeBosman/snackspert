"""Woordenlijsten waarmee posts zonder AI al worden herkend en ingedeeld.

Alles in kleine letters. Pas gerust aan: meer woorden betekent dat de tool
meer oppikt. Een woord mag in meerdere categorieën staan.
"""

# Categorie -> trefwoorden. Het gewicht geeft aan hoe sterk een woord op
# Snackspert-terrein wijst (1.0 = zeker, 0.4 = alleen in combinatie).
CATEGORIES: dict[str, dict[str, float]] = {
    "Friet & frituur": {
        "friet": 1, "patat": 1, "frietje": 1, "frikandel": 1, "frikandelbroodje": 1,
        "kroket": 1, "kroketten": 1, "bitterbal": 1, "bitterballen": 1,
        "kaassoufflé": 1, "kaassouffle": 1, "loempia": 0.8, "berenhap": 1,
        "mexicano": 1, "viandel": 1, "frituur": 1, "snackbar": 1, "cafetaria": 1,
        "vlammetje": 0.8, "vlammetjes": 0.8, "sitostick": 1, "bamischijf": 1,
        "nasischijf": 1, "speciaal": 0.3, "oorlogje": 1, "patatje": 1,
        "frikadel": 1, "kipcorn": 1, "gehaktbal": 0.6, "frites": 0.8,
        "loaded fries": 1, "mayo": 0.4, "frietsaus": 1, "curry": 0.3,
    },
    "Burgers": {
        "burger": 0.9, "burgers": 0.9, "smashburger": 1, "smash burger": 1,
        "cheeseburger": 1, "hamburger": 0.9, "smashed": 0.4,
    },
    "Shoarma, döner & grill": {
        "shoarma": 1, "shawarma": 1, "döner": 1, "doner": 1, "kebab": 1,
        "kapsalon": 1, "dürüm": 1, "durum": 0.8, "gyros": 1, "pita": 0.6,
        "grillroom": 1, "turkse pizza": 1, "lahmacun": 1, "falafel": 0.8,
    },
    "Pizza & Italiaans": {
        "pizza": 0.9, "pizzeria": 1, "calzone": 1, "panuozzo": 1, "focaccia": 0.6,
        "pasta": 0.4,
    },
    "Kip": {
        "fried chicken": 1, "kip": 0.5, "wings": 0.8, "kipnuggets": 1,
        "nuggets": 0.7, "korean fried chicken": 1, "kipsate": 0.7, "tenders": 0.7,
    },
    "Aziatisch": {
        "ramen": 0.9, "sushi": 0.8, "bao": 0.9, "dumplings": 0.9, "dumpling": 0.9,
        "poke": 0.7, "banh mi": 1, "pad thai": 0.8, "gyoza": 0.9, "loempia's": 0.8,
        "kimchi": 0.5, "bibimbap": 0.8, "dim sum": 0.9, "surinaams": 0.8,
        "roti": 0.8, "broodje pom": 1, "pom": 0.3, "bami": 0.6, "nasi": 0.6,
        "saté": 0.6, "sate": 0.4,
    },
    "Mexicaans & Latijns": {
        "taco": 1, "tacos": 1, "burrito": 1, "nachos": 0.8, "quesadilla": 1,
        "birria": 1, "empanada": 1, "arepa": 1,
    },
    "Broodjes & tosti": {
        "broodje": 0.7, "tosti": 0.8, "sandwich": 0.7, "panini": 0.8,
        "broodje kroket": 1, "uitsmijter": 0.6, "hotdog": 1, "hot dog": 1,
        "broodje haring": 0.9, "kibbeling": 1, "lekkerbekje": 1,
    },
    "Zoet & dessert": {
        "donut": 0.8, "donuts": 0.8, "softijs": 1, "ijsje": 0.6, "wafel": 0.7,
        "stroopwafel": 0.9, "poffertjes": 1, "oliebol": 1, "oliebollen": 1,
        "churros": 1, "cookie": 0.5, "cookies": 0.5, "croissant": 0.5,
        "cruffin": 1, "tiramisu": 0.5, "milkshake": 0.8, "bubble tea": 0.9,
        "dubai chocolade": 1, "pistache": 0.4, "crookie": 1, "mochi": 0.8,
        "tompouce": 0.8, "bossche bol": 1, "appeltaart": 0.5,
    },
    "Chips & snacks": {
        "chips": 0.9, "borrelnootjes": 1, "nootjes": 0.6, "popcorn": 0.7,
        "zoutjes": 0.8, "paprikachips": 1, "naturelchips": 1, "ribbelchips": 1,
        "snoep": 0.7, "drop": 0.6, "chocolade": 0.5, "repen": 0.4, "koek": 0.4,
        "koekjes": 0.5, "smaak": 0.3, "snack": 0.8, "snacks": 0.8,
    },
    "Drinken": {
        "frisdrank": 0.7, "energiedrank": 0.8, "energy drink": 0.8, "ijsthee": 0.8,
        "limonade": 0.5, "frappé": 0.6, "iced coffee": 0.6, "matcha": 0.5,
    },
    "Supermarkt & nieuwe producten": {
        "nieuw bij": 1, "nieuw in de supermarkt": 1, "nieuw in het schap": 1,
        "nieuwe smaak": 1, "nieuwe smaken": 1, "limited edition": 0.9,
        "nu verkrijgbaar": 0.8, "in de schappen": 0.9, "net binnen": 0.6,
        "proefpanel": 0.6, "smaaktest": 1, "getest": 0.4, "productreview": 1,
        "supermarkt": 0.8, "huismerk": 0.9, "nieuw product": 1,
        "nieuwe producten": 1, "eerste indruk": 0.6, "first bite": 0.5,
    },
    "Streetfood & events": {
        "streetfood": 1, "street food": 1, "foodtruck": 1, "food truck": 1,
        "foodfestival": 1, "food festival": 1, "foodhall": 1, "food hall": 1,
        "foodmarket": 1, "foodmarkt": 1, "rollende keukens": 1, "kermis": 0.6,
        "eetfestival": 1, "pop-up": 0.5, "popup": 0.5, "nieuwe zaak": 0.9,
        "net geopend": 0.9, "opening": 0.5, "nieuw geopend": 1, "foodspot": 1,
        "foodspots": 1, "hidden gem": 0.6, "foodtour": 1, "food tour": 1,
        "review": 0.5, "beoordeling": 0.4, "foodreview": 1, "food review": 1,
        "foodie": 0.7, "foodies": 0.7, "eten": 0.3, "lekker": 0.2,
    },
}

SUPERMARKETS: dict[str, list[str]] = {
    "Albert Heijn": ["albert heijn", "albertheijn", "ah ", "#ah", "appie", "ahnieuw", "nieuwbijah"],
    "Jumbo": ["jumbo", "jumbosupermarkten"],
    "Lidl": ["lidl", "lidlnederland"],
    "Aldi": ["aldi", "aldinederland"],
    "Plus": ["plus supermarkt", "plussupermarkt", "#plus"],
    "Dirk": ["dirk van den broek", "dirk"],
    "Coop": ["coop supermarkt", "coop"],
    "Spar": ["spar"],
    "Vomar": ["vomar"],
    "Hoogvliet": ["hoogvliet"],
    "DekaMarkt": ["dekamarkt"],
    "Ekoplaza": ["ekoplaza"],
    "Poiesz": ["poiesz"],
    "Jan Linders": ["jan linders", "janlinders"],
    "Picnic": ["picnic"],
    "Action": ["action"],
    "Kruidvat": ["kruidvat"],
}

# Merken die vaak met nieuwe snacks/smaken komen. Herkenning gaat op hele woorden.
BRANDS: list[str] = [
    "Lay's", "Doritos", "Pringles", "Croky", "Smiths", "Cheetos", "Hamka's",
    "Duyvis", "Calvé", "Mora", "Van Dobben", "Kwekkeboom", "Beckers", "Ad van Geloven",
    "Mentos", "Oreo", "Milka", "Tony's Chocolonely", "Verkade", "Lu", "Liga",
    "Ben & Jerry's", "Magnum", "Hertog", "Ola", "Cornetto", "Haribo", "Red Band",
    "Venco", "Katja", "Autodrop", "Snickers", "Twix", "Mars", "KitKat", "M&M's",
    "Coca-Cola", "Fanta", "Pepsi", "Fuze Tea", "Lipton", "Monster", "Red Bull",
    "Rivella", "Chocomel", "Fristi", "Arizona", "Remia", "Heinz", "Unox", "Knorr",
    "Conimex", "Go-Tan", "Iglo", "Aviko", "McCain", "Dr. Oetker", "Ristorante",
    "Wagner", "Bolletje", "Peijnenburg", "Sultana", "Snelle Jelle", "Zwan",
    "Lotus", "Biscoff", "Nutella", "Kinder", "Ferrero", "Daelmans", "Hellmann's",
    "Old El Paso", "Santa Maria", "Ben's Original", "Maggi", "Alpro", "Oatly",
    "Danone", "Campina", "Optimel", "Vifit", "Melkunie", "Mona", "Almhof",
    "Pickwick", "Douwe Egberts", "Nespresso", "Starbucks", "Lavazza", "Tuc",
    "Ritz", "Sun Bites", "Popchips", "Tyrrells", "Kettle", "Brandt", "Grisly",
    "Daim", "Toblerone", "Bounty", "Twix", "Maltesers", "Lion", "Nesquik",
    "Lay’s", "McDonald's", "Burger King", "KFC", "Domino's", "New York Pizza",
    "FEBO", "Smullers", "Kwalitaria", "Cafetaria Sjoerd",
]

# Vaste, nietszeggende hashtags die nooit als trend of bron moeten gelden.
GENERIC_HASHTAGS = {
    "food", "foodie", "foodporn", "instafood", "foodstagram", "yummy", "delicious",
    "instagood", "photooftheday", "love", "reels", "reel", "viral", "explore",
    "explorepage", "fyp", "foryou", "foryoupage", "fy", "tiktok", "trending",
    "instagram", "follow", "like", "likeforlikes", "nederland", "netherlands",
    "holland", "dutch", "nl", "eten", "lekker", "foodlover", "foodblogger",
    "foodphotography", "tasty", "food2go", "eat", "eating", "foodies", "yum",
    "fyp시", "foryourpage", "xyzbca", "capcut", "ad", "reclame", "sponsored",
    "trend", "trendy", "new", "nieuw", "lunch", "dinner", "diner", "ontbijt",
}

# Woorden die op Nederlandstalige tekst wijzen.
DUTCH_WORDS = {
    "de", "het", "een", "en", "van", "is", "niet", "dat", "die", "met", "voor",
    "op", "ook", "maar", "wat", "echt", "lekker", "heel", "deze", "bij", "naar",
    "zijn", "wel", "nog", "nu", "jullie", "wij", "ik", "je", "jij", "mijn", "hier",
    "waar", "kan", "moet", "gaan", "gaat", "geen", "veel", "beste", "smaak",
    "proberen", "geproefd", "eten", "zaak", "broodje", "zo", "erg", "super",
    "vandaag", "gisteren", "morgen", "nieuwe", "nieuw", "eindelijk", "gewoon",
    "hebben", "heb", "hebt", "heeft", "word", "wordt", "kun", "kunnen", "omdat",
    "alleen", "allemaal", "toch", "even", "lekkere", "lekkerste", "goed", "goede",
}

# Woorden in productnamen die geen eten voor mensen zijn ("hondenbrokken met kip").
NON_FOOD = (
    "hond", "kat ", "katten", "kitten", "puppy", "dierenvoer", "brokken", "vogelzaad",
    "knaagdier", "wasmiddel", "wasverzachter", "afwas", "vaatwas", "reiniger", "schoonmaak",
    "toiletpapier", "keukenrol", "shampoo", "douchegel", "deodorant", "tandpasta", "luier",
    "billendoek", "maandverband", "scheer", "make-up", "nagellak", "batterij", "lampen",
    "kaars", "zonnebrand", "bodylotion", "zeep", "wc-", "vuilniszak",
    # dierenvoermerken; niet 'plant' of 'bloem' (plantaardig, bloemkool)
    "sheba", "whiskas", "felix ", "pedigree", "frolic", "kitekat", "jerkies", "dreamies",
)

# Snacks die (bijna) alleen in Nederland en Vlaanderen bestaan: een post die
# hierover gaat is vrijwel zeker Nederlandstalig, ook als hij heel kort is.
DUTCH_FOODS = {
    "frikandel", "kroket", "bitterbal", "kapsalon", "patat", "patatje", "friet", "frietje",
    "snackbar", "frituur", "cafetaria", "kaassoufflé", "kaassouffle", "berenhap", "mexicano",
    "viandel", "bamischijf", "nasischijf", "sitostick", "kipcorn", "oliebol", "stroopwafel",
    "poffertjes", "broodje", "tosti", "softijs", "kibbeling", "lekkerbekje", "hagelslag",
    "speculaas", "tompouce", "appeltaart", "bossche bol", "eierbal", "gehaktbal", "loempia",
}

# Grotere steden met coördinaten voor de kaart.
CITIES: dict[str, tuple[float, float]] = {
    "Amsterdam": (52.3676, 4.9041), "Rotterdam": (51.9244, 4.4777),
    "Den Haag": (52.0705, 4.3007), "Utrecht": (52.0907, 5.1214),
    "Eindhoven": (51.4416, 5.4697), "Groningen": (53.2194, 6.5665),
    "Tilburg": (51.5555, 5.0913), "Almere": (52.3508, 5.2647),
    "Breda": (51.5719, 4.7683), "Nijmegen": (51.8126, 5.8372),
    "Apeldoorn": (52.2112, 5.9699), "Haarlem": (52.3874, 4.6462),
    "Arnhem": (51.9851, 5.8987), "Enschede": (52.2215, 6.8937),
    "Amersfoort": (52.1561, 5.3878), "Zaanstad": (52.4389, 4.8258),
    "Zaandam": (52.4389, 4.8258), "Den Bosch": (51.6978, 5.3037),
    "'s-Hertogenbosch": (51.6978, 5.3037), "Haarlemmermeer": (52.3036, 4.6889),
    "Hoofddorp": (52.3036, 4.6889), "Zwolle": (52.5168, 6.0830),
    "Leiden": (52.1601, 4.4970), "Zoetermeer": (52.0575, 4.4931),
    "Leeuwarden": (53.2012, 5.7999), "Maastricht": (50.8514, 5.6910),
    "Dordrecht": (51.8133, 4.6901), "Ede": (52.0402, 5.6649),
    "Alphen aan den Rijn": (52.1291, 4.6577), "Westland": (51.9912, 4.2089),
    "Alkmaar": (52.6324, 4.7534), "Emmen": (52.7792, 6.9069),
    "Delft": (52.0116, 4.3571), "Venlo": (51.3704, 6.1724),
    "Deventer": (52.2550, 6.1639), "Sittard": (50.9983, 5.8692),
    "Helmond": (51.4793, 5.6570), "Oss": (51.7650, 5.5183),
    "Amstelveen": (52.3114, 4.8701), "Hilversum": (52.2292, 5.1669),
    "Heerlen": (50.8882, 5.9795), "Hengelo": (52.2659, 6.7931),
    "Purmerend": (52.5051, 4.9597), "Roosendaal": (51.5308, 4.4653),
    "Schiedam": (51.9192, 4.3988), "Spijkenisse": (51.8450, 4.3291),
    "Lelystad": (52.5185, 5.4714), "Vlaardingen": (51.9122, 4.3417),
    "Gouda": (52.0115, 4.7104), "Assen": (52.9925, 6.5649),
    "Bergen op Zoom": (51.4949, 4.2911), "Capelle aan den IJssel": (51.9292, 4.5779),
    "Veenendaal": (52.0287, 5.5590), "Katwijk": (52.2034, 4.4165),
    "Zeist": (52.0907, 5.2333), "Nieuwegein": (52.0292, 5.0809),
    "Roermond": (51.1942, 5.9870), "Den Helder": (52.9563, 4.7601),
    "Hoorn": (52.6424, 5.0597), "Middelburg": (51.4988, 3.6136),
    "Vlissingen": (51.4426, 3.5737), "Harderwijk": (52.3417, 5.6206),
    "Wageningen": (51.9692, 5.6654), "Weert": (51.2517, 5.7069),
    "Kampen": (52.5550, 5.9114), "Tiel": (51.8861, 5.4297),
    "Doetinchem": (51.9650, 6.2889), "Heerenveen": (52.9605, 5.9200),
    "Drachten": (53.1077, 6.0985), "Sneek": (53.0326, 5.6589),
    "Scheveningen": (52.1083, 4.2730), "Valkenburg": (50.8650, 5.8320),
}

# Steden die ook als hashtag voorkomen: #eten010 = Rotterdam enz.
CITY_ALIASES: dict[str, str] = {
    "010": "Rotterdam", "020": "Amsterdam", "030": "Utrecht", "070": "Den Haag",
    "040": "Eindhoven", "050": "Groningen", "013": "Tilburg", "076": "Breda",
    "024": "Nijmegen", "026": "Arnhem", "053": "Enschede", "043": "Maastricht",
    "mokum": "Amsterdam", "adam": "Amsterdam", "rdam": "Rotterdam",
    "denhaag": "Den Haag", "thehague": "Den Haag", "dordt": "Dordrecht",
    "denbosch": "Den Bosch", "shertogenbosch": "Den Bosch",
}

# Woorden in een accountnaam die op een (food)zaak wijzen.
# Bewust geen algemene woorden als "friet" of "burger": die staan ook in de
# namen van foodbloggers ("frietkenner"), en dat zijn geen zaken.
BUSINESS_HINTS = [
    "snackbar", "cafetaria", "frietkot", "friettent", "frituur", "grillroom",
    "grillhouse", "shoarmazaak", "shoarma_", "doner_", "kebab_", "kebabhouse",
    "burgerbar", "burgerjoint", "pizzeria", "foodtruck", "taqueria", "eethuis",
    "eetcafe", "lunchroom", "bakkerij", "ijssalon", "gelateria", "snackcorner",
    "smullers", "kwalitaria", "febo", "_grill", "grill_",
]

STOPWORDS = DUTCH_WORDS | {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at",
    "this", "that", "it", "is", "are", "was", "be", "you", "your", "my", "we",
    "our", "so", "too", "very", "just", "all", "from", "by", "as", "if", "me",
    "er", "om", "te", "als", "aan", "dan", "uit", "door", "over", "of", "hun",
    "ze", "zij", "hij", "haar", "hem", "ons", "onze", "we", "wie", "hoe",
    "waarom", "wanneer", "meer", "minder", "mee", "tot", "na", "al", "nou",
    "ja", "nee", "jaa", "haha", "hahaha", "xd", "lol", "omg", "wow", "dus",
    "want", "had", "was", "waren", "werd", "zou", "zal", "wil", "willen",
    "kom", "komt", "komen", "doe", "doet", "doen", "zie", "ziet", "zien",
    "link", "bio", "volg", "volgen", "tag", "check", "klik", "dm", "story",
    "post", "video", "deel", "delen", "insta", "account", "nr", "euro", "€",
}
