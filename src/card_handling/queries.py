import random
from copy import deepcopy

from card_handling.manage_db import DatabaseManager


MODAL_DOUBLE_SIDED_CARDS = ["modal_dfc"] # Cards that can be played on either side
MULTIPLE_FACES_ON_SINGLE_SIDE_CARDS = ["flip", "adventure", "prepare"] # Cards that have multiple faces on one side (front)
DOUBLE_SIDED_ONLY_FRONT_VALID_CARDS = ["transform"] # Cards that can only be played on the front face


def get_random_creature_card(mana_cost: int, 
                             db: DatabaseManager) -> tuple[str, str]:
    """Get data of a random creature card with the specified mana cost from the database. 
    Handles double-faced cards according to the rules for legal token targets in Momir Basic 
    (e.g., for mdfcs, either face can be selected if both are creatures; for transform cards, 
    only the front face can be selected since the back face is not a legal token target; for 
    adventure and prepare cards, the face name is set to None as it is not relevant).
    
    Args:
        mana_cost: The desired mana cost of the creature card.
        db: An instance of the DatabaseManager to query the database.
    Returns:
        tuple: A tuple containing the card name and face name (None if only one face exists).
    """
    result = db.execute_query(
        "SELECT name, type_line, layout FROM cards WHERE type_line LIKE %Creature% AND cmc = ?", 
        (mana_cost,)
    )
    if not result:
        raise ValueError("No matching creature card found")
    
    # Select a random card while handling double-faced cards and skipping illegal cards
    face_name = None
    while True: # loop until legal token target is found
        card_name, type_line, layout = random.choice(result)
        if " // " in type_line: # handle double-faced cards
            name1, name2 = [n.strip() for n in card_name.split(" // ")]
            type1, type2 = [t.strip() for t in type_line.split(" // ")]
            if layout in MODAL_DOUBLE_SIDED_CARDS: # for mdfc cards use the face that is a creature
                if "Creature" in type1:
                    if "Creature" in type2: # select random face if both sides are creatures
                        face_name = random.choice([name1, name2])
                    else:
                        face_name = name1
                else:
                    face_name = name2
            elif layout in DOUBLE_SIDED_ONLY_FRONT_VALID_CARDS: # for transform cards use the front face if it is a creature
                if "Creature" in type1:
                    face_name = name1
                else:
                    continue # skip if front face is not a creature since back face is not a valid token target
            # for other double-faced cards (e.g., adventure, prepare) no face (as in card side) is relevant
        break
    return (card_name, face_name)

def get_card_data(card_name: str, db: DatabaseManager, relevant_face: str = None) -> dict:
    """Get a dictionary containing the standardized card information of a card from the database.
    Handles double-sided cards by using the data from the specified relevant face. 
    Combines data for cards with multiple faces on one side into a single standardized entry 
    where the names and oracle texts are combined, separated by " // ".
    
    Args:
        card_name: The name of the card to query.
        db: An instance of the DatabaseManager to query the database.
        relevant_face: The name of the face to use for double-faced cards.
    Returns:
        dict: A dictionary containing the standardized data of the card.
    """
    result = db.execute_query(
        "SELECT * FROM cards WHERE name = ?", 
        (card_name,)
    )
    if not result:
        raise ValueError("Card not found in database")
    card_data = result[0]
    if card_data.get("name", None) is None: # make sure result contains card data
        raise ValueError("Result does not contain card data")
    return _get_standardized_card_dict(card_data, relevant_face)

def get_mana_cost_range(db: DatabaseManager) -> tuple[int, int]:
    """Get the minimum and maximum mana cost values from the database.
    
    Args:
        db: An instance of the DatabaseManager to query the database.
    Returns:
        tuple: A tuple containing the minimum and maximum mana cost values.
    """
    result = db.execute_query(
        "SELECT MIN(cmc), MAX(cmc) FROM cards WHERE type_line LIKE %Creature%"
    )
    return result[0][0], result[0][1]

def get_nonexistent_creature_mana_costs(db: DatabaseManager) -> list[int]:    
    """Get a list of all creature mana costs that do not exist in the database. 
    Only counts values between the lowest and the highest mana cost in the database.
    
    Args:
        db: An instance of the DatabaseManager to query the database.
    Returns:
        list: A list of the creature mana costs that do not exist in the database.
    """
    result = db.execute_query(
        "SELECT DISTINCT cmc FROM cards WHERE type_line LIKE %Creature%"
    )
    mana_costs = [r[0] for r in result]
    return [cost for cost in range(mana_costs[-1]+1) if cost not in mana_costs]

def _get_standardized_card_dict(card_info: dict, relevant_face: str = None) -> dict:
    """Get a dictionary containing the standardized card information, meaning all relevant keys exist. 
    Handles double-sided cards by using the data from the specified relevant face. 
    Combines data for cards with multiple faces on one side into a single standardized entry 
    where the names and oracle texts are combined, separated by " // ".
    
    Args:
        card_info: A dictionary containing the card information.
        relevant_face: The name of the face to use for double-faced cards.
    Returns:
        dict: A dictionary containing the standardized card information (for the relevant face).
    """
    if card_info["layout"] in MODAL_DOUBLE_SIDED_CARDS and relevant_face is None:
        raise RuntimeError("Relevant face must be specified for modal double-faced cards")
    elif card_info["layout"] in MULTIPLE_FACES_ON_SINGLE_SIDE_CARDS and relevant_face is not None:
        raise RuntimeError("Relevant face should not be specified for cards with multiple faces on one side")
    elif card_info["layout"] in DOUBLE_SIDED_ONLY_FRONT_VALID_CARDS: # only front face matters for transform cards
        relevant_face = card_info["card_faces"][0]
    
    def _combine(key: str) -> str:
        return " // ".join([face[key] for face in card_info["card_faces"]])
    
    card = deepcopy(card_info)
    # If relevant face is given, set all card values to those of that face
    if relevant_face is not None:
        for face in card["card_faces"]:
            if face["name"] == relevant_face:
                for k, v in face.items():
                    card[k] = v
                break
        else:
            raise ValueError(f"Relevant face {relevant_face} not found in card faces")
        # Make sure that power and toughness keys exist
        if "power" not in card:
            card["power"] = ""
        if "toughness" not in card:
            card["toughness"] = ""
    # Handle cards with multiple faces on one side
    elif "card_faces" in card:
        card["name"] = _combine("name")
        card["oracle_text"] = _combine("oracle_text")
        card["mana_cost"] = _combine("mana_cost")
        if "power" in card["card_faces"][0]:
            card["power"] = _combine("power")
        if "toughness" in card["card_faces"][0]:
            card["toughness"] = _combine("toughness")
    # Remove None values and convert all values to strings
    for k, v in card.items():
        if v is None:
            v = ""
        card[k] = str(v).strip()
    return card
