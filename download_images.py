import threading
import timeit
from webserver.load_scryfall_data import load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images


counter = 0
threads = []

start_time = timeit.default_timer()

for card_data in load_scryfall_card_data_chunks("data.json"):
    if ((card_data["layout"] in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"]) 
        or card_data["border_color"] == "silver" 
        or card_data.get("security_stamp", "") == "acorn"
        or card_data["set_type"] in ["memorabilia", "minigame", "alchemy"]
        or card_data.get("digital", False) == True
        or "legal" not in card_data["legalities"].values()):
        continue  # Skip abnormal cards that are not relevant for printing
    image_uris = get_card_image_urls(card_data)

    thread = threading.Thread(target=download_multiple_card_images, args=(image_uris,))
    threads.append(thread)
    thread.start()
    
    if len(threads) >= 100:  # Limit the number of concurrent threads to avoid overwhelming the system
        threads[0].join()  # Wait for the first thread to finish before starting a new one
        threads.pop(0)
    
    counter += 1
    if counter == 1000:
        break
    
for thread in threads:
    thread.join()

end_time = timeit.default_timer()
print(f"Downloaded images for {counter} cards in {end_time - start_time:.4f} seconds")
