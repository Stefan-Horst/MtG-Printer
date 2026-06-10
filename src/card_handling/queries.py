import random
from PIL import Image

from card_handling.manage_db import DatabaseManager
from card_handling.process_image import PRINTER_IMAGE_DIR
from card_handling.load_scryfall_data import MOMIR_AVATAR_NAME


def get_random_creature_card(mana_cost: int, db: DatabaseManager) -> tuple[str, Image.Image]:
    """Get a random creature card printer image with the specified mana cost from the database.
    
    Args:
        mana_cost: The desired mana cost of the creature card.
        db: An instance of the DatabaseManager to query the database.
    Returns:
        tuple: A tuple containing the card name and a PIL Image object representing the card printer image.
    """
    result = db.execute_query(
        "SELECT name FROM cards WHERE type_line LIKE ? AND cmc = ?", 
        ("%Creature%", mana_cost)
    )
    if not result:
        raise ValueError("No matching creature card found")
    card_name = random.choice(result)[0]
    return (card_name, Image.open(f"{PRINTER_IMAGE_DIR}/{card_name}"))

def get_momir_avatar_card() -> tuple[str, Image.Image]:
    """Get the Momir avatar card printer image from the database.
    
    Returns:
        tuple: A tuple containing the card name and a PIL Image object representing the card printer image.
    """
    image_name = MOMIR_AVATAR_NAME
    return (image_name, Image.open(f"{PRINTER_IMAGE_DIR}/{image_name}"))

def get_card_oracle_text(card_name: str, db: DatabaseManager) -> str:
    """Get the oracle text of a card from the database.
    
    Args:
        card_name: The name of the card to query.
        db: An instance of the DatabaseManager to query the database.
    Returns:
        str: The oracle text of the card.
    """
    result = db.execute_query(
        "SELECT oracle_text FROM cards WHERE name = ?", 
        (card_name,)
    )
    if not result:
        raise ValueError("Card not found in database")
    return result[0][0]

def get_momir_avatar_oracle_text(db: DatabaseManager) -> str:
    """Get the oracle text of the Momir avatar card from the database.
    
    Args:
        db: An instance of the DatabaseManager to query the database.
    Returns:
        str: The oracle text of the Momir avatar card.
    """
    return get_card_oracle_text(MOMIR_AVATAR_NAME, db)
