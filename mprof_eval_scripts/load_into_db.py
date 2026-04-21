from webserver.manage_db import create_database, DatabaseManager
from webserver.load_scryfall_data import load_scryfall_card_data_chunks


create_database("cards.db", "webserver/create_db.sql")
db = DatabaseManager("cards.db")
for card_data in load_scryfall_card_data_chunks("data.json"):
    if ((card_data.get("layout") in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"]) 
        or card_data.get("border_color") == "silver" 
        or card_data.get("security_stamp") == "acorn"
        or card_data.get("set_type") in ["memorabilia", "minigame", "alchemy"]):
        continue  # Skip abnormal cards that are not relevant for printing
    try:
        db.save_card_data(card_data, commit=False)
    except Exception as e:
        print(f"### Error saving card data for {card_data.get('name', 'Unknown')}: {e}")
        print(card_data)
        break
db.commit()
db.close()
