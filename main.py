from webserver.load_scryfall_data import download_scryfall_data, load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images
from webserver.manage_db import create_database, DatabaseManager

IMAGE_DOWNLOAD_RETRIES = 10

def main():
    # Step 1: Download card data from Scryfall API and save to JSON file
    print("=> Downloading card data from Scryfall...")
    success = download_scryfall_data()
    if not success:
        print("Failed to download card data from Scryfall. Trying again...")
        success = download_scryfall_data()
        if not success:
            print("Failed to download card data from Scryfall again. Exiting.")
            return
    print("Finished downloading card data.")

    # Step 2: Create a SQLite database and load card data into it; save image URLs for later downloading
    print("=> Loading card data into database...")
    create_database("cards.db", "webserver/create_db.sql", ignore_if_exists=True)
    db = DatabaseManager("cards.db")
    file_image_data = []
    for card_data in load_scryfall_card_data_chunks():
        try:
            db.save_card_data(card_data, commit=False)
        except Exception as e:
            print(f"### Error saving card data for {card_data.get('name', 'Unknown')}: {e}")
        image_urls = get_card_image_urls(card_data)
        file_image_data.extend(image_urls)
    db.commit()
    db.close()
    
    # Step 3: Download card images based on the downloaded card data
    print("=> Downloading card images...")
    failed_downloads = download_multiple_card_images(file_image_data)
    print(f"\nFinished downloading images. {len(failed_downloads)} failed downloads.")
    for i in range(IMAGE_DOWNLOAD_RETRIES):
        if failed_downloads:
            print(f"Retrying failed downloads (attempt {i + 1}/{IMAGE_DOWNLOAD_RETRIES})...")
            failed_downloads = download_multiple_card_images(failed_downloads)
            print(f"Retry finished. {len(failed_downloads)} failed downloads remain.")
        else:
            print("All images downloaded successfully.")
            break
    if failed_downloads:
        print(f"Failed to download images for {len(failed_downloads)} cards. Moving on...")
    
    print("All steps completed. Exiting...")


if __name__ == "__main__":
    main()
