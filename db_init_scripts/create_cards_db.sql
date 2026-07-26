-- Create tables for Magic cards based on Scryfall JSON card data

-- SQLite syntax

CREATE TABLE cards (
    id TEXT PRIMARY KEY, -- Use Scryfall's unique card ID
    -- ignore "object" property
    oracle_id TEXT,
    name TEXT NOT NULL UNIQUE, -- Card names are unique (in theory), business logic relies on this
    layout TEXT NOT NULL,
    mana_cost TEXT,
    cmc REAL NOT NULL,
    type_line TEXT NOT NULL,
    oracle_text TEXT,
    power TEXT,
    toughness TEXT,
    defense TEXT,
    loyalty TEXT,
    flavor_text TEXT,
    flavor_name TEXT,
    hand_modifier TEXT,
    life_modifier TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE card_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ignore "object" property
    card_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mana_cost TEXT NOT NULL,
    cmc REAL,
    flavor_text TEXT,
    defense TEXT,
    power TEXT,
    toughness TEXT,
    loyalty TEXT,
    layout TEXT,
    oracle_id TEXT,
    oracle_text TEXT,
    type_line TEXT,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, name)
);

-- Used for normal cards and card faces of double-faced cards
CREATE TABLE card_image_uris (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL, -- Use PK for card faces, otherwise use card ID
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, type)
);
