import os
import sys
import subprocess

import raspi_io.gpio as gpio
from raspi_io.display import DisplayManager
from raspi_io.printer import PrinterManager
from raspi_io.buttons import ButtonHandler, ButtonState, RotaryEncoderHandler, RotaryState
from raspi_io.background_tasks import toggle_led_blink
from card_handling.load_scryfall_data import download_scryfall_data, load_scryfall_card_data_chunks, get_card_image_urls, download_multiple_card_images
from card_handling.manage_db import DatabaseManager, create_database
from card_handling.process_image import process_all_images


IMAGE_DOWNLOAD_RETRIES = 3
ROTARY_MAX_VALUE = 16 # maximum possible mana cost
ROTARY_MIN_VALUE = 0  # minimum possible mana cost
SKIP_VALUES = [14]    # mana values with no creature cards


def init():
    """Initialize the program by downloading and processing card data and images. 
    This function should be called once at the start of the program."""

    # Step 1: Download card data from Scryfall API and save to JSON file
    print("=> Downloading card data from Scryfall...")
    success = download_scryfall_data()
    if not success:
        print("Failed to download card data from Scryfall. Trying again...")
        success = download_scryfall_data()
        if not success:
            print("Failed to download card data from Scryfall again.\nExiting.")
            sys.exit(1)

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


def main():
    """Main loop of the program, handling button events and updating the display and printer accordingly."""
    
    print("=> Entering main loop. Waiting for button events...")
    global exit_mode
    rotary_value = 0
    try:
        while True:
            # handle main button events: single click to display context info, 
            # double click to display/print general info, long press to exit program and trigger shutdown
            button_state = button_handler.get_state()
            if button_state == ButtonState.SINGLE_CLICK:
                button_handler.reset()
            elif button_state == ButtonState.DOUBLE_CLICK:
                button_handler.reset()
            elif button_state == ButtonState.LONG_PRESS:
                print("=> Shutdown requested. Exiting...")
                exit_mode = "shutdown"
                break # exit program and trigger shutdown
            
            # handle rotary encoder rotations: right rotation increases value, left rotation decreases it;
            # the value wraps around if it would exceed the specified min and max values and specified values are skipped
            rotary_state = rotary_encoder_handler.get_rotary_state()
            if rotary_state == RotaryState.RIGHT:
                rotary_value += 1
                if rotary_value in SKIP_VALUES:
                    rotary_value += 1
                if rotary_value > ROTARY_MAX_VALUE:
                    rotary_value = ROTARY_MIN_VALUE
                rotary_encoder_handler.reset_rotary()
            elif rotary_state == RotaryState.LEFT:
                rotary_value -= 1
                if rotary_value in SKIP_VALUES:
                    rotary_value -= 1
                if rotary_value < ROTARY_MIN_VALUE:
                    rotary_value = ROTARY_MAX_VALUE
                rotary_encoder_handler.reset_rotary()
            
            # handle rotary encoder push button: single click to confirm selected value, 
            # double click currently not used, long press to reset program
            rotary_button_state = rotary_encoder_handler.get_state()
            if rotary_button_state == ButtonState.SINGLE_CLICK:
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.DOUBLE_CLICK:
                # do nothing for now
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.LONG_PRESS:
                rotary_encoder_handler.reset()
    except KeyboardInterrupt:
        print("\n=> Keyboard interrupt received. Exiting...")
    except Exception as e:
        print(f"\n=> An error occurred: {e}\nRestarting...")
        exit_mode = "restart"


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
        toggle_led_blink(True) # blink LED to indicate that the program is running
        display = DisplayManager()
        printer = PrinterManager()
        button_handler = ButtonHandler()
        gpio.add_button_callback(button_handler.button_callback)
        rotary_encoder_handler = RotaryEncoderHandler()
        gpio.add_rotary_callbacks(rotary_encoder_handler.rotary_callback,
                                  rotary_encoder_handler.button_callback)
    except Exception as e:
        print(f"Failed to initialize hardware components: {e}")
        sys.exit(1)
    
    ### INIT DATA
    
    if not args.skipinit:
        init()
    else:
        print("=> Skipping initialization steps...")
    
    ### MAIN LOOP
    
    toggle_led_blink(False) # stop LED blinking after initialization is done
    gpio.toggle_button_led(True) # turn on LED to indicate that the program is ready for input
    db = DatabaseManager()
    exit_mode = ""
    main()
    
    ### CLEANUP

    db.close()
    display.close()
    printer.close()
    gpio.close()

    if exit_mode == "shutdown": # trigger system shutdown
        subprocess.run(["shutdown"])
    elif exit_mode == "restart": # restart the program
        os.execv(sys.executable, ["python3"] + sys.argv + ["-s"])
    else: # key interrupt etc
        sys.exit(0)
