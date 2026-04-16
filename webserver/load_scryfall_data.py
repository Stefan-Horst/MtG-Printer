import json
import time
from pathlib import Path
from io import BytesIO
import requests
from PIL import Image


SCRYFALL_API_URL = "https://api.scryfall.com"
SCRYFALL_HEADERS = {"User-Agent": "MtgMomirPrinter/1.0"}
TIME_BETWEEN_REQUESTS = 100 # milliseconds
BULK_TYPE = "oracle_cards"


def load_scryfall_data(api: str = SCRYFALL_API_URL, 
                       bulk_endpoint: str = "bulk-data", 
                       bulk_type: str = BULK_TYPE,
                       data_dir: str = "./scryfall_data") -> dict:
    """
    Fetch bulk data from Scryfall API with local caching and version checking.
    
    Args:
        api: The Scryfall API URL to fetch bulk data information from
        bulk_endpoint: The endpoint for fetching bulk data information
        bulk_type: The type of bulk data to fetch
        data_dir: Directory to store cached data and metadata
        
    Returns:
        Dictionary containing the Scryfall bulk data
    """
    cache_path = Path(data_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    data_file = cache_path / "cards.json"
    metadata_file = cache_path / "metadata.json"
    
    # Get available bulk data info from API
    bulk_info_url = f"{api}/{bulk_endpoint}"
    response = requests.get(bulk_info_url, headers=SCRYFALL_HEADERS, timeout=5)
    response.raise_for_status()
    bulk_data_info = response.json()
    
    # Find the default cards data
    bulk_data = next(
        (item for item in bulk_data_info["data"] if item["type"] == bulk_type),
        None
    )
    if not bulk_data:
        raise ValueError(f"Data for type '{bulk_type}' not found in Scryfall API")
    
    # Check if local data exists and is up to date
    current_version = bulk_data["updated_at"]
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        if metadata.get("version") == current_version:
            if data_file.exists():
                print(f"Using local up-to-date data (version: {current_version})")
                with open(data_file, "r") as f:
                    return json.load(f)
            else:
                print("Metadata version matches but data file is missing.")
        else:
            print(f"Local data (version: {metadata.get('version')}) is outdated. Using new metadata (version: {current_version})")
            with open(metadata_file, "w") as f:
                json.dump(bulk_data, f)
            
    # Download new data
    print(f"Downloading Scryfall data (version: {current_version})...")
    download_url = bulk_data["download_uri"]
    data_response = requests.get(download_url, headers=SCRYFALL_HEADERS, timeout=5)
    data_response.raise_for_status()
    cards_data = data_response.json()
    
    # Save cards data
    with open(data_file, "w") as f:
        json.dump(cards_data, f)
    print("Data saved successfully")
    return cards_data

def download_multiple_card_images(images_data: list[(str, str)], save_dir: str = "./card_images") -> None:
    """
    Download images for multiple cards from Scryfall and save them locally.
    
    Args:
        images_data: List of tuples with card name and image URL to download
        save_dir: Directory to save the downloaded images
    """
    first = True
    for name, image_url in images_data:
        if not first:
            time.sleep(TIME_BETWEEN_REQUESTS / 1000) # Sleep to respect rate limits
        else:
            first = False
        try:
            download_card_image(name, image_url, save_dir)
        except Exception as e:
            print(f"Failed to download image for {name}: {e}")

def download_card_image(name: str, image_url: str, save_dir: str = "./card_images") -> None:
    """
    Download a card image from Scryfall and save it locally.
    
    Args:
        name: Name of the card (used for saving the image)
        image_url: URL of the card image to download
        save_dir: Directory to save the downloaded image
    """
    response = requests.get(image_url, headers=SCRYFALL_HEADERS, timeout=5)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))
    image.save(f"{save_dir}/{name}.jpg")
