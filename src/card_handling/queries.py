import random
from PIL import Image

from card_handling.manage_db import DatabaseManager
from card_handling.process_image import PRINTER_IMAGE_DIR


def get_random_creature_card(mana_cost: int, db: DatabaseManager) -> Image:
    """Get a random creature card printer image with the specified mana cost from the database.
    
    Args:
        mana_cost: The desired mana cost of the creature card.
        db: An instance of the DatabaseManager to query the database.
    Returns:
        Image: A PIL Image object representing the card printer image.
    """
    result = db.execute_query(
        "SELECT name FROM cards WHERE type_line LIKE ? AND cmc = ?", 
        ("%Creature%", mana_cost)
    )
    if not result:
        raise ValueError("No matching creature card found")
    image_name = random.choice(result)[0]
    return Image.open(f"{PRINTER_IMAGE_DIR}/{image_name}")
