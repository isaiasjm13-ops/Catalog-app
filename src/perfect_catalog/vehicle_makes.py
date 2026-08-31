from __future__ import annotations

"""Curated vehicle-make names and safe aliases used for reviewable suggestions.

This is intentionally not a dump of a VIN database: legal manufacturer names,
trailer builders and ambiguous everyday words would create harmful false matches.
"""

VEHICLE_MAKE_ALIASES: dict[str, str] = {
    # Japan
    "ACURA": "Acura", "DAIHATSU": "Daihatsu", "DATSUN": "Datsun",
    "HON.": "Honda", "HONDA": "Honda", "HINO": "Hino", "INFINITI": "Infiniti",
    "ISUZU": "Isuzu", "LEXUS": "Lexus", "MAZDA": "Mazda",
    "MIT.": "Mitsubishi", "MITS.": "Mitsubishi", "MITSUBISHI": "Mitsubishi",
    "NIS.": "Nissan", "NISS.": "Nissan", "NISSAN": "Nissan",
    "SCION": "Scion", "SUBARU": "Subaru", "SUZUKI": "Suzuki",
    "TOY.": "Toyota", "TOYO.": "Toyota", "TOYOTA": "Toyota",
    # South Korea
    "DAEWOO": "Daewoo", "GENESIS": "Genesis", "HYU.": "Hyundai",
    "HYUNDAI": "Hyundai", "KIA": "Kia", "KGM": "KGM",
    "SSANGYONG": "KGM", "SSANG YONG": "KGM",
    # China
    "BAIC": "BAIC", "BAW": "BAW", "BESTUNE": "Bestune", "BRILLIANCE": "Brilliance",
    "BYD": "BYD", "CHANGAN": "Changan", "CHERY": "Chery", "CHIREY": "Chery",
    "DFM": "Dongfeng", "DFSK": "DFSK", "DONGFENG": "Dongfeng",
    "EXEED": "Exeed", "FAW": "FAW", "FOTON": "Foton", "GAC": "GAC",
    "GEELY": "Geely", "GREAT WALL": "Great Wall", "GWM": "Great Wall",
    "HAVAL": "Haval", "HONGQI": "Hongqi", "JAC": "JAC", "JAECOO": "Jaecoo",
    "JETOUR": "Jetour", "JMC": "JMC", "LI AUTO": "Li Auto", "MAXUS": "Maxus",
    "NIO": "Nio", "OMODA": "Omoda", "ROEWE": "Roewe", "TANK": "Tank",
    "WULING": "Wuling", "XPENG": "XPeng", "ZEEKR": "Zeekr", "ZOTYE": "Zotye",
    # Europe
    "ALFA ROMEO": "Alfa Romeo", "ASTON MARTIN": "Aston Martin", "AUDI": "Audi",
    "BENTLEY": "Bentley", "BMW": "BMW", "CITROEN": "Citroën", "CITROËN": "Citroën",
    "CUPRA": "Cupra", "DACIA": "Dacia", "DS AUTOMOBILES": "DS Automobiles",
    "FERRARI": "Ferrari", "FIAT": "Fiat", "IVECO": "Iveco", "JAGUAR": "Jaguar",
    "LADA": "Lada", "LAMBORGHINI": "Lamborghini", "LAND ROVER": "Land Rover",
    "MASERATI": "Maserati", "MERCEDES": "Mercedes-Benz", "MERCEDES BENZ": "Mercedes-Benz",
    "MERCEDES-BENZ": "Mercedes-Benz", "M.BENZ": "Mercedes-Benz", "OPEL": "Opel",
    "PEUGEOT": "Peugeot", "PORSCHE": "Porsche", "RENAULT": "Renault",
    "SAAB": "Saab", "SCANIA": "Scania", "SKODA": "Škoda", "ŠKODA": "Škoda",
    "VAUXHALL": "Vauxhall", "VOLVO": "Volvo", "VW": "Volkswagen",
    "VOLKSWAGEN": "Volkswagen",
    # Americas
    "BUICK": "Buick", "CADILLAC": "Cadillac", "CHEV.": "Chevrolet",
    "CHEVROLET": "Chevrolet", "CHEVY": "Chevrolet", "CHRYSLER": "Chrysler",
    "DODGE": "Dodge", "FORD": "Ford", "FREIGHTLINER": "Freightliner",
    "GMC": "GMC", "INTERNATIONAL TRUCK": "International", "JEEP": "Jeep",
    "KENWORTH": "Kenworth", "LINCOLN": "Lincoln", "MACK": "Mack",
    "PETERBILT": "Peterbilt", "RIVIAN": "Rivian", "TESLA": "Tesla",
    # India and other high-relevance markets
    "ASHOK LEYLAND": "Ashok Leyland", "MAHINDRA": "Mahindra", "MARUTI": "Maruti Suzuki",
    "MARUTI SUZUKI": "Maruti Suzuki", "PROTON": "Proton", "TATA": "Tata",
}

VEHICLE_MAKES = tuple(sorted(set(VEHICLE_MAKE_ALIASES.values()), key=str.casefold))
