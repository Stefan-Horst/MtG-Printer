import sys
import subprocess

from card_handling.load_scryfall_data import download_scryfall_data, load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images
from card_handling.manage_db import DatabaseManager, create_database
from card_handling.process_image import process_all_images


IMAGE_DOWNLOAD_RETRIES = 3


# Step 1: Download card data from Scryfall API and save to JSON file
print("=> Downloading card data from Scryfall...")
success = download_scryfall_data()
if not success:
    print("Failed to download card data from Scryfall. Trying again...")
    success = download_scryfall_data()
    if not success:
        print("Failed to download card data from Scryfall again.\nExiting.")
        sys.exit(1)
print("Finished downloading card data.")

# Step 2: Create a SQLite database and load card data into it; save image URLs for later downloading
print("=> Loading card data into database...")
create_database(ignore_if_exists=True)
db = DatabaseManager()
file_image_data = []
for card_data in load_scryfall_card_data_chunks():
    try:
        db.save_card_data(card_data, commit=False, handle_exist="ignore")
    except Exception:
        print(f"Failed to save card data for {card_data.get('name', 'Unknown')}. Trying again...")
        try:
            db.save_card_data(card_data, commit=False, handle_exist="ignore")
        except Exception as e:
            print(f"Failed to save card data for {card_data.get('name', 'Unknown')}: {e}")
    image_urls = get_card_image_urls(card_data)
    file_image_data.extend(image_urls)
try:
    db.commit()
except Exception:
    print("Failed to commit changes to database. Trying again...")
    try:
        db.commit()
    except Exception as e:
        print(f"Failed to commit changes to database: {e}\nExiting.")
        db.close()
        sys.exit(1)
db.close()

# Step 3: Download card images based on the downloaded card data
print("=> Downloading card images...")
failed_downloads = download_multiple_card_images(file_image_data, skip_existing=True)
print(f"Finished downloading images. {len(failed_downloads)} failed downloads.")
for i in range(IMAGE_DOWNLOAD_RETRIES):
    if failed_downloads:
        print(f"Retrying failed downloads (attempt {i + 1}/{IMAGE_DOWNLOAD_RETRIES})...")
        failed_downloads = download_multiple_card_images(failed_downloads, skip_existing=True)
        print(f"Retry finished. {len(failed_downloads)} failed downloads remain.")
    else:
        print("All images downloaded successfully.")
        break
if failed_downloads:
    print(f"Failed to download images for {len(failed_downloads)} cards. Moving on...")

# Step 4: Process downloaded images (turn into high-contrast black & white versions)
print("=> Processing card images...")
try:
    process_all_images(skip_existing=True)
except Exception:
    print("Failed to process images. Trying again...")
    try:
        process_all_images(skip_existing=True)
    except Exception as e:
        print(f"Failed to process images: {e}\nExiting.")
        sys.exit(1)

print("All steps completed. Exiting...")
