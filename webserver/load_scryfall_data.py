import json
import time
import asyncio
from pathlib import Path
from io import BytesIO
from collections.abc import Generator
import requests
import aiohttp
from splitstream import splitfile
from PIL import Image


IMAGE_DIR = "./card_images"
DATA_DIR = "./card_data"
METADATA_FILE = "metadata.json"
DATA_FILE = "cards.json"

BULK_TYPE = "oracle_cards"
IMAGE_TYPE = "border_crop"
SCRYFALL_API_URL = "https://api.scryfall.com"
BULK_DATA_ENDPOINT = "bulk-data"
SCRYFALL_HEADERS = {"User-Agent": "MtgMomirPrinter/1.0"}
TIMEOUT = 20 # seconds
TIME_BETWEEN_REQUESTS = 100 # milliseconds
CHUNK_SIZE = 1024 * 1024 * 10 # 10 MB
MAX_CONCURRENT_DOWNLOADS = 100 # limit for concurrent image downloads
IMAGES_BATCH_SIZE = 500 # number of images to download at once in the async function

### JSON CARD DATA FILE LOADING

def load_scryfall_card_data_chunks(filepath: str = DATA_DIR+"/"+DATA_FILE, exclude_invalid: bool = True) -> Generator[dict, None, None]:
    """
    Load card data from a JSON file in chunks of single card dicts to limit memory usage.
    
    Args:
        filepath: The path to the JSON file containing card data
        exclude_invalid: If True, skip cards that are not considered valid for printing
        
    Returns:
        A generator that yields a dictionary containing the loaded card data for each card in the file
    """
    with open(filepath, "r") as f:
        for card in splitfile(f, format="json", startdepth=1):
            card_data = json.loads(card)
            if not exclude_invalid or _is_card_valid(card_data):
                yield card_data

def _is_card_valid(card_data: dict) -> bool:
    """Check if a card is valid for saving based on its properties.
    This is used to filter out special cards that are not relevant for printing 
    (e.g, art series, playtest cards, un-cards, and other cards not used in normal play).
    
    Args:
        card_data: The dictionary containing the card data for a single card
        
    Returns:
        True if the card is valid for printing, False otherwise
    """

    if (# cards not legal in any format
        "legal" not in card_data["legalities"].values() 
        # card types not played in any normal format
        or card_data["layout"] in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"] 
        # digital cards
        or card_data.get("digital", False) == True
        # un-cards
        or card_data["border_color"] == "silver" 
        or card_data.get("security_stamp") == "acorn"
        # special collector & minigame cards
        or set(card_data.get("promo_types", [])) & {"playtest", "plastic", "alchemy"}
        or card_data["set_type"] in ["memorabilia", "minigame", "alchemy"]):
        return False
    return True

### JSON CARD DATA DOWNLOADING

def download_scryfall_data(api: str = SCRYFALL_API_URL, 
                           bulk_endpoint: str = BULK_DATA_ENDPOINT, 
                           bulk_type: str = BULK_TYPE,
                           data_dir: str = DATA_DIR,
                           force_update: bool = False) -> bool:
    """
    Fetch bulk data info from Scryfall API and download new card data 
    if downloaded info is more recent than local info.
    
    Args:
        api: The Scryfall API URL
        bulk_endpoint: The endpoint for fetching bulk data and its info
        bulk_type: The type of bulk data to fetch
        data_dir: Directory to store data and metadata
        force_update: If True, forces downloading new data even if local data is up to date
        
    Returns:
        True if data was successfully loaded or already up to date, False otherwise
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    data_file = data_path / DATA_FILE
    metadata_file = data_path / METADATA_FILE
    
    # Get available bulk data info from API
    bulk_info_url = f"{api}/{bulk_endpoint}"
    response = requests.get(bulk_info_url, headers=SCRYFALL_HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    bulk_types_info = response.json()
    
    # Find the default cards data
    bulk_data_info = next(
        (item for item in bulk_types_info["data"] if item["type"] == bulk_type),
        None
    )
    if not bulk_data_info:
        print(f"Data for type '{bulk_type}' not found in Scryfall API")
        return False
    
    # Check if local metadata and data exists and is up to date
    current_version = bulk_data_info["updated_at"]
    if not force_update and metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        if metadata.get("updated_at") == current_version:
            if data_file.exists():
                print(f"Using local up-to-date data (version: {current_version})")
                return True
            else:
                print("Metadata version matches but data file is missing.")
        else:
            print(f"Local metadata (version: {metadata.get('updated_at')}) is outdated. Using new metadata (version: {current_version})")
            with open(metadata_file, "w") as f:
                json.dump(bulk_data_info, f)
    else:
        print(f"No local metadata found. Using new metadata (version: {current_version})")
        with open(metadata_file, "w") as f:
            json.dump(bulk_data_info, f)
    
    # Download new card data
    print(f"Downloading card data (version: {current_version})...")
    download_url = bulk_data_info["download_uri"]
    try:
        _download_data_in_chunks(download_url, data_file, SCRYFALL_HEADERS)
    except Exception:
        print("Failed to download data. Trying again...")
        time.sleep(TIME_BETWEEN_REQUESTS / 1000)
        try:
            _download_data_in_chunks(download_url, data_file, SCRYFALL_HEADERS)
        except Exception as e:
            print(f"Failed to download data again: {e}")
            return False
    return True

def _download_data_in_chunks(url: str, filepath: str, headers: dict) -> None:
    """
    Download data from a URL in chunks and save it to a file, limiting memory usage.
    
    Args:
        url: The URL to download the data from
        filepath: The path to the file where the data will be saved
        headers: Optional headers to include in the request
    """
    with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)

### CARD IMAGES

def download_images_from_card_data_list(card_data: list[dict], skip_existing: bool = True) -> list[tuple[str, str]]:
    """
    Download card images from Scryfall for a list of cards.
    
    Args:
        card_data: The list of dictionaries containing card data for multiple cards
        skip_existing: If True, skip downloading images that already exist in the directory
    
    Returns:
        List of tuples with card name and image URL that failed to download
    """
    image_data = []
    for card in card_data:
        image_urls = get_card_image_urls(card)
        image_data.extend(image_urls)
    return download_multiple_card_images(image_data, skip_existing=skip_existing)

def download_images_from_card_data_file(filepath: str = DATA_DIR+"/"+DATA_FILE, skip_existing: bool = True) -> list[tuple[str, str]]:
    """
    Download card images from Scryfall for all cards in a JSON file.
    
    Args:
        filepath: The path to the JSON file containing card data
        skip_existing: If True, skip downloading images that already exist in the directory
    
    Returns:
        List of tuples with card name and image URL that failed to download
    """
    file_image_data = []
    for card_data in load_scryfall_card_data_chunks(filepath):
        image_urls = get_card_image_urls(card_data)
        file_image_data.extend(image_urls)
    return download_multiple_card_images(file_image_data, skip_existing=skip_existing)

def download_multiple_card_images(images_data: list[tuple[str, str]], 
                                  batch_size: int = IMAGES_BATCH_SIZE, 
                                  image_dir: str = IMAGE_DIR, 
                                  skip_existing: bool = True) -> list[tuple[str, str]]:
    """
    Download images for multiple cards from Scryfall and save them locally. 
    Wrapper function to run the async download function.
    
    Args:
        images_data: List of tuples with card name and image URL to download
        batch_size: Number of images to download at once (used for batching in the async function)
        image_dir: Directory to save the downloaded images
        skip_existing: If True, skip downloading images that already exist in the directory
    Returns:
        List of tuples with card name and image URL that failed to download
    """
    return asyncio.run(_download_multiple_card_images(images_data, batch_size, image_dir, skip_existing))

async def _download_multiple_card_images(images_data: list[tuple[str, str]], 
                                         batch_size: int = IMAGES_BATCH_SIZE, 
                                         image_dir: str = IMAGE_DIR, 
                                         skip_existing: bool = True) -> list[tuple[str, str]]:
    """
    Download images for multiple cards from Scryfall and save them locally. 
    Uses async pattern to speed up the process.
    
    Args:
        images_data: List of tuples with card name and image URL to download
        batch_size: Number of images to download at once (used for batching in the async function)
        image_dir: Directory to save the downloaded images
        skip_existing: If True, skip downloading images that already exist in the directory
    
    Returns:
        List of tuples with card name and image URL that failed to download
    """
    image_dir = Path(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    if skip_existing:
        existing_images = {file.stem for file in image_dir.glob("*.jpg")}
        images_data = [(name, url) for name, url in images_data if name not in existing_images]
        print(f"Skipping {len(existing_images)} existing images. Downloading {len(images_data)} new images...")
    failed_downloads = []
    conn = aiohttp.TCPConnector(limit_per_host=MAX_CONCURRENT_DOWNLOADS)
    async with aiohttp.ClientSession(connector=conn) as session:
        batch_amount = (len(images_data) + batch_size - 1) // batch_size
        for i in range(0, len(images_data), batch_size):
            print(f"Downloading image batch {i//batch_size + 1}/{batch_amount}...")
            chunk = images_data[i:i+batch_size]
            tasks = [_download_card_image(name, url, session, image_dir) for name, url in chunk]
            results = await asyncio.gather(*tasks)
            fails = [result for result in results if result != (None, None)]
            print(f"Finished downloading batch. {len(fails)} failed downloads.")
            failed_downloads.extend(fails)
    return failed_downloads

async def _download_card_image(name: str, image_url: str, session: aiohttp.ClientSession, image_dir: str = IMAGE_DIR) -> tuple[str, str]:
    """
    Download a card image from Scryfall and save it locally. 
    Must be called within an aiohttp client session.
    
    Args:
        name: Name of the card (used for saving the image)
        image_url: URL of the card image to download
        session: aiohttp client session to use for the request
        image_dir: Directory to save the downloaded image
    
    Returns:
        A tuple of (name, image_url) if the download failed, or (None, None) if it succeeded
    """
    try:
        async with session.get(image_url, headers=SCRYFALL_HEADERS, timeout=TIMEOUT, raise_for_status=True) as response:
            content = await response.read()
    except Exception as e:
        if len(str(e)) > 0:
            print(f"Failed to download image for {name}: {str(e)}")
        return (name, image_url)
    name = name.replace("/", "_").replace('"', "").replace("?", "").replace(":", "").strip()
    image = Image.open(BytesIO(content))
    image.save(f"{image_dir}/{name}.jpg")
    return (None, None)

def get_card_image_urls(card_data: dict, image_type: str = IMAGE_TYPE) -> list[tuple[str, str]]:
    """
    Get the image URLs and names of the card faces for a card from its data dictionary.
    
    Args:
        card_data: The dictionary containing the card data for a single card
        image_type: The type of image to retrieve (e.g., "border_crop", "large", "normal", "small", "png")
    
    Returns:
        A list of tuples containing the name and image URLs for the card
    """
    urls = []
    if "image_uris" in card_data:
        urls.append((card_data["name"], card_data["image_uris"][image_type]))
    elif "card_faces" in card_data:
        for face in card_data["card_faces"]:
            urls.append((face["name"], face["image_uris"][image_type]))
    return urls
