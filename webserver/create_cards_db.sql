-- Create tables for Magic cards based on Scryfall JSON card data

-- SQLite syntax

CREATE TABLE cards (
    id TEXT PRIMARY KEY, -- Use Scryfall's unique card ID
    -- ignore "object" property
    oracle_id TEXT,
    arena_id INTEGER,
    resource_id TEXT,
    name TEXT NOT NULL,
    lang TEXT NOT NULL,
    released_at TEXT NOT NULL,
    uri TEXT NOT NULL,
    scryfall_uri TEXT NOT NULL,
    layout TEXT NOT NULL,
    highres_image INTEGER NOT NULL, --Boolean
    image_status TEXT NOT NULL,
    mana_cost TEXT,
    cmc REAL NOT NULL,
    type_line TEXT NOT NULL,
    oracle_text TEXT,
    power TEXT,
    toughness TEXT,
    defense TEXT,
    loyalty TEXT,
    rarity TEXT NOT NULL,
    artist TEXT,
    illustration_id TEXT,
    border_color TEXT NOT NULL,
    frame TEXT,
    security_stamp TEXT,
    card_back_id TEXT, -- Actually can be null for double-faced cards
    set_id TEXT NOT NULL,
    set_ TEXT NOT NULL, -- "set" is a reserved keyword
    set_name TEXT NOT NULL,
    set_type TEXT NOT NULL,
    set_uri TEXT NOT NULL,
    set_search_uri TEXT NOT NULL,
    scryfall_set_uri TEXT NOT NULL,
    rulings_uri TEXT NOT NULL,
    prints_search_uri TEXT NOT NULL,
    watermark TEXT,
    flavor_text TEXT,
    flavor_name TEXT,
    printed_name TEXT,
    printed_text TEXT,
    printed_type_line TEXT,
    hand_modifier TEXT,
    life_modifier TEXT,
    mtgo_id INTEGER,
    mtgo_foil_id INTEGER,
    tcgplayer_id INTEGER,
    tcgplayer_etched_id INTEGER,
    cardmarket_id INTEGER,
    digital INTEGER NOT NULL, --Boolean
    collector_number TEXT NOT NULL,
    edhrec_rank INTEGER,
    penny_rank INTEGER,
    reserved INTEGER, --Boolean
    game_changer INTEGER, --Boolean
    oversized INTEGER NOT NULL, --Boolean
    promo INTEGER NOT NULL, --Boolean
    reprint INTEGER NOT NULL, --Boolean
    variation INTEGER NOT NULL, --Boolean
    variation_of TEXT,
    full_art INTEGER NOT NULL, --Boolean
    textless INTEGER NOT NULL, --Boolean
    booster INTEGER NOT NULL, --Boolean
    story_spotlight INTEGER NOT NULL, --Boolean
    content_warning INTEGER, --Boolean
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE card_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ignore "object" property
    card_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mana_cost TEXT NOT NULL,
    artist TEXT,
    artist_id TEXT,
    cmc REAL,
    flavor_text TEXT,
    defense TEXT,
    power TEXT,
    toughness TEXT,
    loyalty TEXT,
    illustration_id TEXT,
    layout TEXT,
    oracle_id TEXT,
    oracle_text TEXT,
    printed_name TEXT,
    printed_text TEXT,
    printed_type_line TEXT,
    type_line TEXT,
    watermark TEXT,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, name)
);

-- Used for normal cards and card faces of double-faced cards
CREATE TABLE card_colors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL, -- Use PK for card faces, otherwise use card ID
    color TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, color)
);

-- Used for normal cards and card faces of double-faced cards
CREATE TABLE card_color_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL, -- Use PK for card faces, otherwise use card ID
    color TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, color)
);

-- Used for normal cards and card faces of double-faced cards
CREATE TABLE card_color_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL, -- Use PK for card faces, otherwise use card ID
    color TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, color)
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

CREATE TABLE card_artist_ids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, artist_id)
);

CREATE TABLE card_frame_effects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    frame_effect TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, frame_effect)
);

CREATE TABLE card_finishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    finish TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, finish)
);

CREATE TABLE card_produced_mana (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    color TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, color)
);

CREATE TABLE card_legalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    format TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, format)
);

CREATE TABLE card_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    game TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, game)
);

CREATE TABLE card_multiverse_ids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    multiverse_id INTEGER NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, multiverse_id)
);

CREATE TABLE card_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, keyword)
);

-- Related cards (like created tokens)
CREATE TABLE card_all_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ignore "object" property
    card_id TEXT NOT NULL,
    component TEXT NOT NULL,
    name TEXT NOT NULL,
    type_line TEXT NOT NULL,
    uri TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, uri)
);

CREATE TABLE card_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    type TEXT NOT NULL,
    price REAL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, type)
);

CREATE TABLE card_related_uris (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, type)
);

CREATE TABLE card_purchase_uris (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, type)
);

CREATE TABLE card_previews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    previewed_at TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, source_uri)
);

CREATE TABLE card_promo_types(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    type TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, type)
);

CREATE TABLE card_attraction_lights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    number TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(card_id, number)
);
