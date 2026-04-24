import asyncio
import timeit
from io import BytesIO
import aiohttp
from PIL import Image
from webserver.load_scryfall_data import load_scryfall_card_data_chunks, get_card_image_urls, SCRYFALL_HEADERS, TIMEOUT, IMAGE_DIR


async def download_all_images():
    counter = 0
    data = []
    for card_data in load_scryfall_card_data_chunks("data.json"):
        if ((card_data["layout"] in ["art_series", "scheme", "vanguard", "planar", "double_faced_token"]) 
            or card_data["border_color"] == "silver" 
            or card_data.get("security_stamp", "") == "acorn"
            or card_data["set_type"] in ["memorabilia", "minigame", "alchemy"]
            or card_data.get("digital", False) == True
            or "legal" not in card_data["legalities"].values()):
            continue  # Skip abnormal cards that are not relevant for printing
        image_uris = get_card_image_urls(card_data)
        data.extend(image_uris)
        
        counter += 1
        if counter == 1000:
            break

    def _make_filename_valid(name: str) -> str:
        return name.replace("/", "_").replace('"', "").replace("?", "").replace(":", "").strip()

    async with aiohttp.ClientSession() as session:
        tasks = [download_image(url, _make_filename_valid(name), session) for name, url in data]
        await asyncio.gather(*tasks)

async def download_image(url, name, session):
    async with session.get(url, headers=SCRYFALL_HEADERS, timeout=TIMEOUT, raise_for_status=True) as response:
        try:
            content = await response.read()
        except Exception:
            print(f"Failed to download image for {name}. Trying again...")
            await asyncio.sleep(100 / 1000)
            try:
                async with session.get(url, headers=SCRYFALL_HEADERS, timeout=TIMEOUT, raise_for_status=True) as response:
                    content = await response.read()
            except Exception as e:
                print(f"Failed to download image for {name} again: {e}")
                return
    image = Image.open(BytesIO(content))
    image.save(f"{IMAGE_DIR}/{name}.jpg")

async def main():
    start_time = timeit.default_timer()
    
    await download_all_images()

    end_time = timeit.default_timer()
    print(f"Downloaded in {end_time - start_time:.4f} seconds")

asyncio.run(main())
