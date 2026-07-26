### SCRIPT FOR RUNNING INITIALIZATION INDIVIDUALLY WITHOUT DEVICE HARDWARE REQUIREMENTS ###
# You might want to use this if your device has limited compute to speed 
# up the initialization process and then just transfer the files (the data dir)


from card_handling.load_scryfall_data import IMAGE_TYPE_FULL, IMAGE_TYPE_ART, _SUPPORTED_IMAGE_TYPES
from main import _init_scryfall_data, _init_db, _init_card_images, _init_image_processing, has_internet_connection, cleanup


def init(image_download_types: list[str] = _SUPPORTED_IMAGE_TYPES) -> bool:
    """Initialize the program by downloading and processing card data and images. 
    This function should be called once at the start of the program.
    
    Args:
        image_download_types: List of image types to download (e.g., ["border_crop", "art_crop"]).
    
    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    if not all(image_type in _SUPPORTED_IMAGE_TYPES for image_type in image_download_types):
        print(f"Error: Unsupported image type(s) specified. Supported types are: {_SUPPORTED_IMAGE_TYPES}")
        return False
    image_type_data = {image_type: [] for image_type in image_download_types}
    
    # Step 1: Download card data from Scryfall API and save to JSON file
    success = _init_scryfall_data()
    if not success:
        return False

    # Step 2: Create a SQLite database and load card data into it; save image URLs for later downloading
    success, image_type_data = _init_db(image_type_data)
    if not success:
        return False

    # Step 3: Download card images based on the downloaded card data
    success = _init_card_images(image_type_data)
    if not success:
        return False

    # Step 4: Process downloaded images (turn into high-contrast black & white versions)
    success = _init_image_processing(image_download_types)
    if not success:
        return False
    return True


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--imgtypes", nargs="+", default=_SUPPORTED_IMAGE_TYPES, choices=_SUPPORTED_IMAGE_TYPES, type=str, 
                        help=f"Specify which image types to download and process. Supported types: {_SUPPORTED_IMAGE_TYPES}")
    args = parser.parse_args()
    
    print("=> Starting initialization individually...")
    
    enabled_image_types = args.imgtypes
    if enabled_image_types == [IMAGE_TYPE_FULL]:
        print("=> Using only full card images for printing.")
    elif enabled_image_types == [IMAGE_TYPE_ART]:
        print("=> Using only art crop images for printing.")
    
    ### INIT DATA
    
    init_success = False
    if has_internet_connection():
        init_success = init(enabled_image_types)
    else:
        print("=> No internet connection detected.")
    
    if init_success:
        print("===> Initialization successful.")
    else:
        print("===> Initialization failed.")
    
    ### CLEANUP

    cleanup()
