import random
from PIL import Image

from card_handling.manage_db import DatabaseManager
from card_handling.process_image import PRINTER_IMAGE_DIR
from card_handling.load_scryfall_data import MOMIR_AVATAR_NAME, make_filename_valid


def get_random_creature_card(mana_cost: int, db: DatabaseManager) -> tuple[str, Image.Image]:
    """Get a random creature card printer image with the specified mana cost from the database. 
    Handles double-faced cards according to the rules for legal token targets in Momir Basic 
    (e.g., for mdfcs, either face can be selected if both are creatures; for transform cards, 
    only the front face can be selected since the back face is not a legal token target; for 
    adventure and prepare cards, the primary face containing the creature is selected).
    
    Args:
        mana_cost: The desired mana cost of the creature card.
        db: An instance of the DatabaseManager to query the database.
    Returns:
        tuple: A tuple containing the card name and a PIL Image object representing the card printer image.
    """
    result = db.execute_query(
        "SELECT name, type_line, layout FROM cards WHERE type_line LIKE ? AND cmc = ?", 
        ("%Creature%", mana_cost)
    )
    if not result:
        raise ValueError("No matching creature card found")
    
    # Select a random card while handling double-faced cards and skipping illegal cards
    while True: # loop until legal token target is found
        card_name, type_line, layout = random.choice(result)
        if " // " in type_line: # handle double-faced cards
            name1, name2 = [n.strip() for n in card_name.split(" // ")]
            type1, type2 = [t.strip() for t in type_line.split(" // ")]
            if layout == "modal_dfc": # for mdfc cards use the face that is a creature
                if "Creature" in type1:
                    if "Creature" in type2: # select random face if both sides are creatures
                        face_name = random.choice([name1, name2])
                    else:
                        face_name = name1
                else:
                    face_name = name2
            elif layout == "transform": # for transform cards use the front face if it is a creature
                if "Creature" in type1:
                    face_name = name1
                else:
                    continue # skip if front face is not a creature since back face is not a valid token target
            else: # for other double-faced cards (e.g., adventure, prepare) just select the first face as default
                if "Creature" in type1:
                    face_name = name1
                else: # edge case that should theoretically not exist
                    face_name = name2
        break
    
    img_name = make_filename_valid(face_name)
    return (face_name, Image.open(f"{PRINTER_IMAGE_DIR}/{img_name}"))

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

def get_nonexistent_creature_mana_costs(db: DatabaseManager) -> list[int]:    
    """Get a list of all creature mana costs that do not exist in the database. 
    Only counts values between the lowest and the highest mana cost in the database.
    
    Args:
        db: An instance of the DatabaseManager to query the database.
    Returns:
        list: A list of the creature mana costs that do not exist in the database.
    """
    result = db.execute_query(
        "SELECT DISTINCT cmc FROM cards WHERE type_line LIKE ?", 
        ("%Creature%",)
    )
    mana_costs = [r[0] for r in result]
    return [cost for cost in range(mana_costs[-1]+1) if cost not in mana_costs]
