import socket

from card_handling.load_scryfall_data import IMAGE_DIR, download_scryfall_data, load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images, clear_local_data
from card_handling.manage_db import DatabaseManager, create_database
from card_handling.process_image import PRINTER_IMAGE_DIR, process_all_images


IMAGE_DOWNLOAD_RETRIES = 3
CONNECTION_TEST_HOST = "1.1.1.1" # host to test internet connection against (Cloudflare DNS)


def init_scryfall_data() -> bool:
    """Download card data from Scryfall API and save to JSON file. Retrys the download once if it fails.
    
    Returns:
        bool: True if data was successfully downloaded, False otherwise.
    """
    print("=> Downloading card data from Scryfall...")
    success = download_scryfall_data()
    if not success:
        print("Failed to download card data from Scryfall. Trying again...")
        success = download_scryfall_data()
        if not success:
            print("Failed to download card data from Scryfall again.\nExiting.")
            return False
    return True

def init_db(image_type_data: dict[str, list[tuple[str, str]]]) -> tuple[bool, dict[str, list[tuple[str, str]]]]:
    """Create a SQLite database and load card data into it. Save image URLs for later downloading.
    
    Args:
        image_type_data: Dictionary mapping image types to currently empty lists of image URLs.
    
    Returns:
        A tuple of the dict and a boolean being True if data was successfully loaded into the database, False otherwise.
    """
    print("=> Loading card data into database...")
    try:
        create_database(ignore_if_exists=True)
        db = DatabaseManager()
    except Exception as e:
        print(f"Failed to create or open database: {e}.\nExiting.")
        return False, image_type_data
    
    for card_data in load_scryfall_card_data_chunks():
        try:
            db.save_card_data(card_data, commit=False, handle_exist="ignore")
        except Exception:
            print(f"Failed to save card data for {card_data.get('name', 'Unknown')}. Trying again...")
            try:
                db.save_card_data(card_data, commit=False, handle_exist="ignore")
            except Exception as e:
                print(f"Failed to save card data for {card_data.get('name', 'Unknown')}: {e}.\nExiting.")
                clear_local_data() # remove card data to avoid inconsistent state on next run
                return False, image_type_data
        for image_type, image_urls in image_type_data.items():
            image_urls.extend(get_card_image_urls(card_data, image_type))
    
    try:
        db.commit()
    except Exception:
        print("Failed to commit changes to database. Trying again...")
        try:
            db.commit()
        except Exception as e:
            print(f"Failed to commit changes to database: {e}\nExiting.")
            clear_local_data() # remove card data to avoid inconsistent state on next run
            return False, None
    db.close()
    return True, image_type_data

def init_card_images(image_type_data: dict[str, list[tuple[str, str]]]) -> bool:
    """Download card images from Scryfall for a list of cards.
    
    Args:
        image_type_data: Dictionary mapping image types to lists of image URLs.
    
    Returns:
        bool: True if images were successfully downloaded, False otherwise.
    """
    print("=> Downloading card images...")
    for image_type, image_urls in image_type_data.items():
        failed_downloads = download_multiple_card_images(image_urls, image_dir=IMAGE_DIR+"/"+image_type, skip_existing=True)
        print(f"Finished downloading {image_type} images. {len(failed_downloads)} failed downloads.")
        for i in range(IMAGE_DOWNLOAD_RETRIES):
            if failed_downloads:
                print(f"Retrying failed downloads (attempt {i + 1}/{IMAGE_DOWNLOAD_RETRIES})...")
                failed_downloads = download_multiple_card_images(failed_downloads, image_dir=IMAGE_DIR+"/"+image_type, skip_existing=True)
                print(f"Retry finished. {len(failed_downloads)} failed downloads remain.")
            else:
                print(f"All {image_type} images downloaded successfully.")
                break
        if failed_downloads:
            print(f"Failed to download {image_type} images for {len(failed_downloads)} cards. Exiting.")
            clear_local_data() # remove card data to avoid inconsistent state on next run
            return False
    return True

def init_image_processing(image_download_types: list[str], device_width: int) -> bool:
    """Process downloaded images (turn into high-contrast black & white versions).
    
    Args:
        image_download_types: List of image types to process.
        device_width: Width of the printer in pixels
    
    Returns:
        bool: True if images were successfully processed, False otherwise.
    """
    print("=> Processing card images...")
    for image_type in image_download_types:
        try:
            process_all_images(device_width, IMAGE_DIR+"/"+image_type, PRINTER_IMAGE_DIR+"/"+image_type, skip_existing=True)
        except Exception as e:
            print(f"Failed to process {image_type} images: {e}\nExiting.")
            clear_local_data() # remove card data to avoid inconsistent state on next run
            return False
    return True

def has_internet_connection() -> bool:
    """Check if there is an active internet connection by trying to connect to a known host. 
    Not fail-safe, only checks a specific host and port, but is sufficient in this context.
    
    Returns:
        bool: True if there is an internet connection, False otherwise.
    """
    try:
        s = socket.create_connection((CONNECTION_TEST_HOST, 80), timeout=1)
        s.close()
        return True
    except Exception:
        print("No internet connection. Trying again...")
        try:
            s = socket.create_connection((CONNECTION_TEST_HOST, 80), timeout=1)
            s.close()
            return True
        except Exception:
            print("No internet connection detected.")
    return False
