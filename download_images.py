from webserver.load_scryfall_data import load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images


for card_data in load_scryfall_card_data_chunks("data.json"):
    if ((card_data["layout"] in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"]) 
        or card_data["border_color"] == "silver" 
        or card_data.get("security_stamp") == "acorn"
        or card_data["set_type"] in ["memorabilia", "minigame", "alchemy"]):
        continue  # Skip abnormal cards that are not relevant for printing
    image_uris = get_card_image_urls(card_data)
    download_multiple_card_images(image_uris)
