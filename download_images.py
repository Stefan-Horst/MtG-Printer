import multiprocessing
from webserver.load_scryfall_data import load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images

if __name__ == "__main__":
    url_list = []
    for card_data in load_scryfall_card_data_chunks("data.json"):
        if ((card_data["layout"] in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"]) 
            or card_data["border_color"] == "silver" 
            or card_data.get("security_stamp") == "acorn"
            or card_data["set_type"] in ["memorabilia", "minigame", "alchemy"]
            or "legal" not in card_data["legalities"].values()):
            continue  # Skip abnormal cards that are not relevant for printing
        image_uris = get_card_image_urls(card_data)
        url_list.append(image_uris)

    print(f"Downloading {len(url_list)} images...")
    url_list = url_list[:1000]  # Limit to first 1000 images for testing

    print(f"Using {multiprocessing.cpu_count()} CPU cores for downloading...")
    with multiprocessing.Pool() as pool:
        pool.map(download_multiple_card_images, url_list)
