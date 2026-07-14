import os
import sys
import subprocess
import socket
import time
from typing import Literal

import raspi_io.gpio as gpio
from raspi_io.display import DisplayManager
from raspi_io.printer import PrinterManager
from raspi_io.buttons import ButtonHandler, ButtonState, RotaryEncoderHandler, RotaryState
from card_handling.load_scryfall_data import IMAGE_DIR, IMAGE_TYPE_FULL, IMAGE_TYPE_ART, _SUPPORTED_IMAGE_TYPES, download_scryfall_data, load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images, clear_local_data
from card_handling.manage_db import DatabaseManager, create_database
from card_handling.process_image import PRINTER_IMAGE_DIR, process_all_images
from card_handling.queries import get_random_creature_card, get_momir_avatar_card, get_card_data, get_standardized_card_dict, get_nonexistent_creature_mana_costs, get_mana_cost_range


IMAGE_DOWNLOAD_RETRIES = 3
CONNECTION_TEST_HOST = "1.1.1.1" # host to test internet connection against (Cloudflare DNS)


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
    
    # Step 1: Download card data from Scryfall API and save to JSON file
    print("=> Downloading card data from Scryfall...")
    display.display_loading_screen("[1/4] Downloading card data...", size=1)
    success = download_scryfall_data()
    if not success:
        print("Failed to download card data from Scryfall. Trying again...")
        success = download_scryfall_data()
        if not success:
            print("Failed to download card data from Scryfall again.\nExiting.")
            return False

    # Step 2: Create a SQLite database and load card data into it; save image URLs for later downloading
    print("=> Loading card data into database...")
    display.display_loading_screen("[2/4] Loading data into db...", size=2)
    try:
        create_database(ignore_if_exists=True)
        db = DatabaseManager()
    except Exception as e:
        print(f"Failed to create or open database: {e}.\nExiting.")
        return False
    
    image_type_data = {image_type: [] for image_type in image_download_types}
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
                return False
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
            return False
    db.close()

    # Step 3: Download card images based on the downloaded card data
    print("=> Downloading card images...")
    display.display_loading_screen("[3/4] Downloading card images...", size=3)
    for image_type, image_urls in image_type_data.items():
        success = _download_images_with_retries(image_urls, IMAGE_DIR+"/"+image_type, image_type)
        if not success:
            return False

    # Step 4: Process downloaded images (turn into high-contrast black & white versions)
    print("=> Processing card images...")
    display.display_loading_screen("[4/4] Processing card images...", size=4)
    for image_type, image_urls in image_type_data.items():
        success = _process_images_with_retries(IMAGE_DIR+"/"+image_type, PRINTER_IMAGE_DIR+"/"+image_type, image_type)
        if not success:
            return False
    return True

def _download_images_with_retries(image_data_list: list[tuple[str, str]], 
                                  image_dir: str, 
                                  images_name: str) -> bool:
    """
    Download card images from Scryfall with retries for failed downloads.
    
    Args:
        image_data_list: List of tuples containing card names and image URLs to download.
        image_dir: Directory to save the downloaded images.
        images_name: Name of the image type being downloaded (e.g., "border_crop", "art_crop").

    Returns:
        bool: True if all images were downloaded successfully, False otherwise.
    """
    failed_downloads = download_multiple_card_images(image_data_list, image_dir=image_dir, skip_existing=True)
    print(f"Finished downloading {images_name} images. {len(failed_downloads)} failed downloads.")
    for i in range(IMAGE_DOWNLOAD_RETRIES):
        if failed_downloads:
            print(f"Retrying failed downloads (attempt {i + 1}/{IMAGE_DOWNLOAD_RETRIES})...")
            failed_downloads = download_multiple_card_images(failed_downloads, image_dir=image_dir, skip_existing=True)
            print(f"Retry finished. {len(failed_downloads)} failed downloads remain.")
        else:
            print(f"All {images_name} images downloaded successfully.")
            break
    if failed_downloads:
        print(f"Failed to download {images_name} images for {len(failed_downloads)} cards. Exiting.")
        clear_local_data() # remove card data to avoid inconsistent state on next run
        return False # failure
    return True # success

def _process_images_with_retries(image_dir: str, output_dir: str, images_name: str) -> bool:
    """
    Process card images to create high-contrast black & white versions optimized for printing, with retries for failed processing.
    
    Args:
        image_dir: Directory containing the source images.
        output_dir: Directory to save the processed images.
        images_name: Name of the image type being processed (e.g., "border_crop", "art_crop").

    Returns:
        bool: True if all images were processed successfully, False otherwise.
    """
    try:
        process_all_images(image_dir, output_dir, skip_existing=True)
    except Exception as e:
        print(f"Failed to process {images_name} images: {e}\nExiting.")
        clear_local_data() # remove card data to avoid inconsistent state on next run
        return False
    return True


def main() -> Literal["shutdown", "restart", "exit"]:
    """Main loop of the program, handling button events and updating the display and printer accordingly.
    This function runs indefinitely until a shutdown or restart is triggered by a button event or an error occurs.
    
    Returns:
        Literal["shutdown", "restart", "exit"]: The exit mode indicating the requested action.
    """
    print("=> Entering main loop. Waiting for button events...")
    display.display_text("~ Momir Vig ~\nReady for input!")
    rotary_min_value, rotary_max_value = get_mana_cost_range(db)
    skip_values = get_nonexistent_creature_mana_costs(db)
    rotary_value = 0
    current_card = None
    current_face = None
    full_print_mode = True # if True, print full card image; if False, print text with art crop
    try:
        while True:
            # handle main button events: single click to display context info, 
            # double click to display/print general info, long press to exit program and trigger shutdown
            button_state = button_handler.get_state()
            if button_state == ButtonState.SINGLE_CLICK:
                # SHOW CARD CONTEXT INFO
                if current_card:
                    gpio.toggle_led_blink(True) # make LED blink while busy
                    card_info = get_card_data(current_card, db)
                    card_info = get_standardized_card_dict(card_info, current_face)
                    display.display_card_info(card_info)
                    gpio.toggle_led_blink(False)
                    gpio.toggle_button_led(True) # turn button LED back on after loading screen
                else:
                    display.display_text("No card printed yet.\nPress the button to print a card.")
                button_handler.reset()
            elif button_state == ButtonState.DOUBLE_CLICK:
                # SWITCH TO PRINT TEXT MODE
                full_print_mode = not full_print_mode
                if full_print_mode:
                    display.display_text("Switched to full card print mode.")
                else:
                    display.display_text("Switched to text print mode.")
                button_handler.reset()
            elif button_state == ButtonState.LONG_PRESS:
                # SHUTDOWN
                display.display_text("Shutting down...")
                print("=> Shutdown requested. Exiting...")
                time.sleep(1)
                return "shutdown" # exit program and trigger shutdown
            
            # handle rotary encoder rotations: right rotation increases value, left rotation decreases it;
            # the value wraps around if it would exceed the specified min and max values and specified values are skipped
            rotary_state = rotary_encoder_handler.get_rotary_state()
            if rotary_state == RotaryState.RIGHT:
                # INCREASE VALUE
                rotary_value += 1
                if rotary_value in skip_values:
                    rotary_value += 1
                if rotary_value > rotary_max_value:
                    rotary_value = rotary_min_value
                display.display_text(f"Mana Cost: {rotary_value}")
                rotary_encoder_handler.reset_rotary()
            elif rotary_state == RotaryState.LEFT:
                # DECREASE VALUE
                rotary_value -= 1
                if rotary_value in skip_values:
                    rotary_value -= 1
                if rotary_value < rotary_min_value:
                    rotary_value = rotary_max_value
                display.display_text(f"Mana Cost: {rotary_value}")
                rotary_encoder_handler.reset_rotary()
            
            # handle rotary encoder push button: single click to confirm selected value, 
            # double click currently not used, long press to reset program
            rotary_button_state = rotary_encoder_handler.get_state()
            if rotary_button_state == ButtonState.SINGLE_CLICK:
                # PRINT RANDOM CARD
                gpio.toggle_led_blink(True)
                size = max(1, rotary_value // 2) # thicker loading bars for higher mana costs
                display.display_loading_screen(f"Printing a {rotary_value} cost creature!", size=size)
                img_dir = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_FULL if full_print_mode else PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_ART
                current_card, current_face, card_img = get_random_creature_card(rotary_value, db, img_dir)
                if full_print_mode:
                    printer.print_card_image(card_img)
                else:
                    card_info = get_card_data(current_card, db)
                    card_info = get_standardized_card_dict(card_info, current_face)
                    printer.print_card(card_info, card_img)
                display.stop_loading_screen()
                gpio.toggle_led_blink(False)
                gpio.toggle_button_led(True)
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.DOUBLE_CLICK:
                # PRINT MOMIR AVATAR CARD
                gpio.toggle_led_blink(True)
                display.display_loading_screen("Printing Momir Avatar!")
                img_dir = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_FULL if full_print_mode else PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_ART
                current_card, momir_img = get_momir_avatar_card(img_dir)
                current_face = None
                if full_print_mode:
                    printer.print_card_image(momir_img)
                else:
                    card_info = get_card_data(current_card, db)
                    card_info = get_standardized_card_dict(card_info, current_face)
                    printer.print_card(card_info, momir_img)
                display.stop_loading_screen()
                gpio.toggle_led_blink(False)
                gpio.toggle_button_led(True)
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.LONG_PRESS:
                # RESTART PROGRAM
                display.display_text("Restarting program...")
                print("=> Restart requested. Exiting...")
                time.sleep(1)
                return "restart"
    except KeyboardInterrupt:
        print("\n=> Keyboard interrupt received. Exiting...")
    except Exception as e:
        print(f"\n=> An error occurred: {e}\nRestarting...")
        display.display_text("An error occurred.\nRestarting...")
        time.sleep(3) # wait a moment to allow the user to see the message on the display before restarting
        return "restart"
    return "exit" # just exit the program

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

def cleanup() -> None:
    """Clean up resources on program exit."""
    try: db.close()
    except Exception: pass
    try: printer.close() 
    except Exception: pass
    try: display.close() 
    except Exception: pass
    try: gpio.close() 
    except Exception: pass


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--skipinit", default=False, action="store_true", help="Skip initialization steps")
    args = parser.parse_args()
    
    ### INIT AND CHECK HARDWARE COMPONENTS

    print("=> Initializing hardware components...")
    try:
        gpio.setup_gpio()
        gpio.toggle_led_blink(True) # blink LED to indicate that the program is running
        display = DisplayManager()
        printer = PrinterManager()
        button_handler = ButtonHandler()
        gpio.add_button_callback(button_handler.button_callback)
        rotary_encoder_handler = RotaryEncoderHandler()
        gpio.add_rotary_callbacks(rotary_encoder_handler.rotary_callback,
                                  rotary_encoder_handler.button_callback)
    except Exception as e:
        print(f"Failed to initialize hardware components: {e}")
        cleanup()
        subprocess.run(["shutdown"]) # shut down because user cannot be shown error message on display and would not know what is happening otherwise
    
    ### INIT DATA
    
    if not args.skipinit:
        display.display_text("Startup successful.\nBeginning initialization.")
        time.sleep(1) # wait a moment to give user chance to press button for skipping initialization steps if desired
    
    init_success = True # only false if initialization steps were attempted and then failed
    if args.skipinit or button_handler.is_pressed():
        print("=> Skipping initialization steps...")
    elif has_internet_connection():
        init_success = init()
    else:
        print("=> No internet connection detected. Skipping initialization steps...")
    gpio.toggle_led_blink(False) # stop LED blinking after initialization is done
    
    # Restart the program to try initialization again on next run or shutdown if button pressed
    if not init_success: 
        gpio.toggle_led_blink(True, interval=0.2) # blink LED rapidly to indicate initialization failure
        if button_handler.is_pressed():
            print("=> Initialization failed. Manually shutting down...")
            display.display_text("Init failed.\nShutting down...")
            exit_mode = "shutdown"
        else:
            print("=> Initialization failed. Restarting...")
            display.display_text("Init failed.\nRestarting...")
            exit_mode = "restart"
        time.sleep(3) # wait a moment to allow the user to see the message on the display before restarting or shutting down
    
    ### MAIN LOOP
    
    if init_success: # Only enter main loop if initialization was successful
        gpio.toggle_button_led(True) # turn on LED to indicate that the program is ready for input
        db = DatabaseManager()
        exit_mode = main()    
    
    ### CLEANUP

    cleanup()
    if exit_mode == "shutdown": # trigger system shutdown
        subprocess.run(["shutdown"])
    elif exit_mode == "restart": # restart the program
        os.execv(sys.executable, ["python3"] + sys.argv + ["-s"])
    else: # key interrupt etc
        sys.exit(0)
