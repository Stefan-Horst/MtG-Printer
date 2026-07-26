import sqlite3
from pathlib import Path
from typing import Literal

from . import DATA_PATH, PROJECT_PATH


DB_DIR = str(DATA_PATH / "db")
DB_FILE = "cards.db"
SCHEMA_DIR = str(PROJECT_PATH / "db_init_scripts")
SCHEMA_FILE = "create_cards_db.sql"


def create_database(db_dir: str = DB_DIR, 
                    filename: str = DB_FILE, 
                    schema_path: str = SCHEMA_DIR+"/"+SCHEMA_FILE, 
                    ignore_if_exists: bool = True) -> None:
    """Create a SQLite database from a SQL schema file.
    
    Args:
        db_dir: Directory where the database file will be created
        filename: Name of the database file to create
        schema_path: Path to the SQL schema file
        ignore_if_exists: If True, do nothing if the db already exists. If False, delete the db and create a new one.
    """
    db_path = Path(db_dir)
    db_path.mkdir(parents=True, exist_ok=True)
    db_file = db_path / filename
    if db_file.exists():
        if ignore_if_exists:
            return # executing code below would raise an exception
        else:
            db_file.unlink() # delete existing db to create a new one

    conn = sqlite3.connect(db_file)
    with open(schema_path, "r") as f:
        schema = f.read()
    conn.executescript(schema)
    conn.commit()
    conn.close()


class DatabaseManager:
    """A class to manage database connections and operations for the card data."""
    
    def __init__(self, db_path: str = DB_DIR+"/"+DB_FILE):
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
    
    def execute_query(self, query: str, 
                      params: tuple = (), 
                      commit: bool = False) -> list[tuple]:
        """Execute a SQL query with optional parameters and commit.
        
        Args:
            query: The SQL query to execute, with ? placeholders for parameters
            params: A tuple of parameters to substitute into the query
            commit: Whether to commit the transaction after executing the query
        
        Returns:
            A list of tuples representing the rows returned by the query (if any)
        """
        if not self.cursor:
            self.create_cursor()
        self.cursor.execute(query, params)
        if commit:
            self.commit()
        return self.cursor.fetchall()
    
    def close(self) -> None:
        self.conn.close()
    
    def save_cards_data(self, cards: list[dict], 
                        commit: bool = True, 
                        handle_exist: Literal["ignore", "replace", "fail"] = "ignore") -> None:
        """Save a list of cards into the database.
        
        Args:
            cards: A list of dictionaries containing the card data
            commit: Whether to commit the transaction
            handle_exist: How to handle if the card already exists in the database.
                "ignore": Do nothing and keep the existing card (default)
                "replace": Replace the existing card with the new one
                "fail": Raise an exception if the card already exists
        """
        exist_clause = {
            "ignore": "OR IGNORE ",
            "replace": "OR REPLACE ",
            "fail": "",
        }[handle_exist]
        
        if not self.cursor:
            self.create_cursor()
        self._insert_cards_into_db(cards, exist_clause)
        if commit:
            self.commit()

    def _insert_cards_into_db(self, cards: list[dict], handle_exist_clause: str) -> None:
        # Insert main card data
        self.cursor.executemany(f"""
            INSERT {handle_exist_clause}INTO cards (
                id, oracle_id, name, layout, mana_cost, cmc, type_line, 
                oracle_text, power, toughness, defense, loyalty, 
                flavor_text, flavor_name, hand_modifier, life_modifier, 
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(
                card.get("id"),
                card.get("oracle_id"),
                card.get("name"),
                card.get("layout"),
                card.get("mana_cost"),
                card.get("cmc"),
                card.get("type_line"),
                card.get("oracle_text"),
                card.get("power"),
                card.get("toughness"),
                card.get("defense"),
                card.get("loyalty"),
                card.get("flavor_text"),
                card.get("flavor_name"),
                card.get("hand_modifier"),
                card.get("life_modifier")
            ) for card in cards]
        )
                
        # Insert related data into junction tables
        self.cursor.executemany(f"""
            INSERT {handle_exist_clause}INTO card_faces (
                card_id, name, mana_cost, cmc, flavor_text, 
                defense, power, toughness, loyalty, layout, 
                oracle_id, oracle_text, type_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
                [
                    (
                        card.get("id"),
                        face.get("name"),
                        face.get("mana_cost"),
                        face.get("cmc"),
                        face.get("flavor_text"),
                        face.get("defense"),
                        face.get("power"),
                        face.get("toughness"),
                        face.get("loyalty"),
                        face.get("layout"),
                        face.get("oracle_id"),
                        face.get("oracle_text"),
                        face.get("type_line")
                    ) for face in card["card_faces"]
                ] for card in cards
        ])
        
        self.cursor.executemany(f"""
            INSERT {handle_exist_clause}INTO card_image_uris (card_id, type, uri) 
            VALUES (?, ?, ?)""", [
                [
                    (card.get("id"), card_type, uri) for card_type, uri in card["image_uris"].items()
                ] for card in cards
            ]
        )
