"""Public field guide: numerical traits and descriptive growing advice."""
SPECIES_GUIDE = {
    "moss": {"name": "Velvet moss", "moisture": 65, "shade": 67, "upkeep": 2,
             "lifespan": 105, "harvest_age": 8, "yield": 2, "resource": "fiber",
             "description": "A soft pioneer for cool, shaded soil."},
    "fern": {"name": "Glass fern", "moisture": 58, "shade": 55, "upkeep": 3,
             "lifespan": 105, "harvest_age": 12, "yield": 3, "resource": "fiber",
             "description": "Tall fronds shelter a damp woodland floor."},
    "clover": {"name": "Sun clover", "moisture": 45, "shade": 20, "upkeep": 2,
               "lifespan": 105, "harvest_age": 6, "yield": 2, "resource": "nectar",
               "description": "A bright clearing plant that feeds visiting bees."},
    "glowcap": {"name": "Lantern glowcap", "moisture": 72, "shade": 82, "upkeep": 3,
                "lifespan": 75, "harvest_age": 10, "yield": 2, "resource": "spores",
                "description": "A dusk fungus happiest in wet, deep shade."},
}
TERRAINS = {
    "soil": {"evaporation": 0, "rain_bonus": 0, "plantable": True, "description": "Balanced earth."},
    "sand": {"evaporation": 3, "rain_bonus": -2, "plantable": True, "description": "Fast draining, sun warmed sand."},
    "peat": {"evaporation": -1, "rain_bonus": 3, "plantable": True, "description": "Water holding organic ground."},
    "pond": {"evaporation": 0, "rain_bonus": 0, "plantable": False, "description": "Open water; holds 100 moisture."},
    "stone": {"evaporation": 0, "rain_bonus": 0, "plantable": False, "description": "A dry, unplantable stepping stone."},
}
RECIPES = {
    "compost": {"cost": {"fiber": 3}, "makes": {"compost": 2}},
    "mulch": {"cost": {"fiber": 2}, "makes": {"mulch": 3}},
    "tonic": {"cost": {"nectar": 2, "spores": 1}, "makes": {"tonic": 1}},
}
RESOURCES = ("fiber", "nectar", "spores", "compost", "mulch", "tonic")
STRUCTURES = ("none", "shade_cloth", "rain_barrel", "bee_house", "log")
LAYERS = ("art", "moisture", "nutrients", "shade", "vitality", "mulch", "stress", "terrain")


def field_guide():
    import copy
    return copy.deepcopy({"species": SPECIES_GUIDE, "terrains": TERRAINS,
                          "recipes": RECIPES, "structures": STRUCTURES, "layers": LAYERS})
