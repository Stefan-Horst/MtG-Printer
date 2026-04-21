import requests

bulk_info_url = "https://api.scryfall.com/bulk-data"
response = requests.get(bulk_info_url, timeout=5)
response.raise_for_status()
bulk_data_info = response.json()
bulk_data = next(
        (item for item in bulk_data_info["data"] if item["type"] == "oracle_cards"),
        None
    )
download_url = bulk_data["download_uri"]
with requests.get(download_url, stream=True) as response:
        response.raise_for_status()
        with open("data.json", 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024*10):  # 10 MB chunks
                f.write(chunk)
