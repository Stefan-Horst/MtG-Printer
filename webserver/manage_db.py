import sqlite3


def create_database(db_path: str, schema_path: str) -> None:
    """Create a SQLite database from a SQL schema file.
    
    Args:
        db_path: Path to the database file to create
        schema_path: Path to the SQL schema file
    """
    conn = sqlite3.connect(db_path)
    with open(schema_path, "r") as f:
        schema = f.read()
    conn.executescript(schema)
    conn.commit()
    conn.close()


class DatabaseManager:
    """A class to manage database connections and operations for the card data."""
    
    def __init__(self, db_path: str):
        """Initialize a new DatabaseManager instance.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = None
    
    def create_cursor(self) -> None:
        self.cursor = self.conn.cursor()
    
    def commit(self) -> None:
        """Commit the current transaction to the database and reset the cursor."""
        self.conn.commit()
        self.cursor = None
    
    def close(self) -> None:
        self.conn.close()
        
    def save_card_data(self, card: dict, commit: bool = True) -> None:
        """Save a single card into the database.
        
        Args:
            card: A dictionary containing the card data
            commit: Whether to commit the transaction
        """
        if not self.cursor:
            self.create_cursor()
        self._insert_card_into_db(card)
        if commit:
            self.commit()

    def _insert_card_into_db(self, card: dict) -> None:
        card_id = card.get("id")
        # Insert main card data
        self.cursor.execute("""
            INSERT INTO cards (
                id, oracle_id, arena_id, resource_id, name, lang, released_at, uri, 
                scryfall_uri, layout, highres_image, image_status, mana_cost, cmc, 
                type_line, oracle_text, power, toughness, defense, loyalty, rarity, 
                artist, illustration_id, border_color, frame, security_stamp, 
                card_back_id, set_id, set_, set_name, set_type, set_uri, 
                set_search_uri, scryfall_set_uri, rulings_uri, prints_search_uri, 
                watermark, flavor_text, flavor_name, printed_name, printed_text, 
                printed_type_line, hand_modifier, life_modifier, mtgo_id, 
                mtgo_foil_id, tcgplayer_id, tcgplayer_etched_id, cardmarket_id, 
                digital, collector_number, edhrec_rank, penny_rank, reserved, 
                game_changer, oversized, promo, reprint, variation, variation_of, 
                full_art, textless, booster, story_spotlight, content_warning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_id,
            card.get("oracle_id"),
            card.get("arena_id"),
            card.get("resource_id"),
            card.get("name"),
            card.get("lang"),
            card.get("released_at"),
            card.get("uri"),
            card.get("scryfall_uri"),
            card.get("layout"),
            card.get("highres_image"),
            card.get("image_status"),
            card.get("mana_cost"),
            card.get("cmc"),
            card.get("type_line"),
            card.get("oracle_text"),
            card.get("power"),
            card.get("toughness"),
            card.get("defense"),
            card.get("loyalty"),
            card.get("rarity"),
            card.get("artist"),
            card.get("illustration_id"),
            card.get("border_color"),
            card.get("frame"),
            card.get("security_stamp"),
            card.get("card_back_id"),
            card.get("set_id"),
            card.get("set"),
            card.get("set_name"),
            card.get("set_type"),
            card.get("set_uri"),
            card.get("set_search_uri"),
            card.get("scryfall_set_uri"),
            card.get("rulings_uri"),
            card.get("prints_search_uri"),
            card.get("watermark"),
            card.get("flavor_text"),
            card.get("flavor_name"),
            card.get("printed_name"),
            card.get("printed_text"),
            card.get("printed_type_line"),
            card.get("hand_modifier"),
            card.get("life_modifier"),
            card.get("mtgo_id"),
            card.get("mtgo_foil_id"),
            card.get("tcgplayer_id"),
            card.get("tcgplayer_etched_id"),
            card.get("cardmarket_id"),
            card.get("digital"),
            card.get("collector_number"),
            card.get("edhrec_rank"),
            card.get("penny_rank"),
            card.get("reserved"),
            card.get("game_changer"),
            card.get("oversized"),
            card.get("promo"),
            card.get("reprint"),
            card.get("variation"),
            card.get("variation_of"),
            card.get("full_art"),
            card.get("textless"),
            card.get("booster"),
            card.get("story_spotlight"),
            card.get("content_warning")
        ))
                
        # Insert related data into junction tables
        if "card_faces" in card:
            for face in card["card_faces"]:
                self.cursor.execute("""
                    INSERT INTO card_faces (
                        card_id, name, mana_cost, artist, artist_id, cmc, flavor_text, 
                        defense, power, toughness, loyalty, illustration_id, layout, 
                        oracle_id, oracle_text, printed_name, printed_text, 
                        printed_type_line, type_line, watermark
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    card_id,
                    face.get("name"),
                    face.get("mana_cost"),
                    face.get("artist"),
                    face.get("artist_id"),
                    face.get("cmc"),
                    face.get("flavor_text"),
                    face.get("defense"),
                    face.get("power"),
                    face.get("toughness"),
                    face.get("loyalty"),
                    face.get("illustration_id"),
                    face.get("layout"),
                    face.get("oracle_id"),
                    face.get("oracle_text"),
                    face.get("printed_name"),
                    face.get("printed_text"),
                    face.get("printed_type_line"),
                    face.get("type_line"),
                    face.get("watermark")
                ))
        
        if "colors" in card:
            for color in card["colors"]:
                self.cursor.execute("""INSERT INTO card_colors (card_id, color) 
                                       VALUES (?, ?)""", (card_id, color))
        
        if "color_identities" in card:
            for color in card["color_identities"]:
                self.cursor.execute("""INSERT INTO card_color_identities (card_id, color) 
                                       VALUES (?, ?)""", (card_id, color))
        
        if "color_indicators" in card:
            for color in card["color_indicators"]:
                self.cursor.execute("""INSERT INTO card_color_indicators (card_id, color) 
                                       VALUES (?, ?)""", (card_id, color))
        
        if "image_uris" in card:
            for type, uri in card["image_uris"].items():
                self.cursor.execute("""INSERT INTO card_image_uris (card_id, type, uri) 
                                       VALUES (?, ?, ?)""", (card_id, type, uri))
        
        if "artist_ids" in card:
            for artist_id in card["artist_ids"]:
                self.cursor.execute("""INSERT INTO card_artist_ids (card_id, artist_id) 
                                       VALUES (?, ?)""", (card_id, artist_id))
        
        if "frame_effects" in card:
            for frame_effect in card["frame_effects"]:
                self.cursor.execute("""INSERT INTO card_frame_effects (card_id, frame_effect) 
                                       VALUES (?, ?)""", (card_id, frame_effect))
        
        if "finishes" in card:
            for finish in card["finishes"]:
                self.cursor.execute("""INSERT INTO card_finishes (card_id, finish) 
                                       VALUES (?, ?)""", (card_id, finish))
        
        if "produced_mana" in card:
            for color in card["produced_mana"]:
                self.cursor.execute("""INSERT INTO card_produced_mana (card_id, color) 
                                       VALUES (?, ?)""", (card_id, color))
        
        if "legalities" in card:
            for format, status in card["legalities"].items():
                self.cursor.execute("""INSERT INTO card_legalities (card_id, format, status) 
                                       VALUES (?, ?, ?)""", (card_id, format, status))
        
        if "games" in card:
            for game in card["games"]:
                self.cursor.execute("""INSERT INTO card_games (card_id, game) 
                                       VALUES (?, ?)""", (card_id, game))
        
        if "multiverse_ids" in card:
            for multiverse_id in card["multiverse_ids"]:
                self.cursor.execute("""INSERT INTO card_multiverse_ids (card_id, multiverse_id) 
                                       VALUES (?, ?)""", (card_id, multiverse_id))
        
        if "keywords" in card:
            for keyword in card["keywords"]:
                self.cursor.execute("""INSERT INTO card_keywords (card_id, keyword) 
                                       VALUES (?, ?)""", (card_id, keyword))
        
        if "all_parts" in card:
            for part in card["all_parts"]:
                self.cursor.execute("""
                    INSERT INTO card_all_parts (
                        card_id, component, name, type_line, uri
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                        card_id, 
                        part.get("component"), 
                        part.get("name"), 
                        part.get("type_line"), 
                        part.get("uri")
                ))
        
        if "prices" in card:
            for type, price in card["prices"].items():
                if price is not None:
                    self.cursor.execute("""INSERT INTO card_prices (card_id, type, price) 
                                           VALUES (?, ?, ?)""", (card_id, type, price))
        
        if "related_uris" in card:
            for type, uri in card["related_uris"].items():
                self.cursor.execute("""INSERT INTO card_related_uris (card_id, type, uri) 
                                       VALUES (?, ?, ?)""", (card_id, type, uri))
        
        if "purchase_uris" in card:
            for type, uri in card["purchase_uris"].items():
                self.cursor.execute("""INSERT INTO card_purchase_uris (card_id, type, uri) 
                                       VALUES (?, ?, ?)""", (card_id, type, uri))
        
        if "previews" in card:
            preview = card["previews"]
            self.cursor.execute("""
                INSERT INTO card_previews (
                    card_id, source, source_uri, previewed_at
                ) VALUES (?, ?, ?, ?)
            """, (
                card_id,
                preview.get("source"),
                preview.get("source_uri"),
                preview.get("previewed_at")
            ))
        
        if "promo_types" in card:
            for type in card["promo_types"]:
                self.cursor.execute("""INSERT INTO card_promo_types (card_id, type) 
                                       VALUES (?, ?)""", (card_id, type))
        
        if "attraction_lights" in card:
            for number in card["attraction_lights"]:
                self.cursor.execute("""INSERT INTO card_attraction_lights (card_id, number) 
                                       VALUES (?, ?)""", (card_id, number))
