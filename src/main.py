import os
import sys
import subprocess
import time
from typing import Literal

import raspi_io.gpio as gpio
from raspi_io.display import DisplayManager
from raspi_io.printer import PrinterManager
from raspi_io.buttons import ButtonHandler, ButtonState, RotaryEncoderHandler, RotaryState
from card_handling.load_scryfall_data import MOMIR_AVATAR_NAME, IMAGE_TYPE_FULL, IMAGE_TYPE_ART, _SUPPORTED_IMAGE_TYPES
from card_handling.manage_db import DatabaseManager
from card_handling.process_image import get_card_image_for_mode
from card_handling.queries import get_random_creature_card, get_card_data, get_nonexistent_creature_mana_costs, get_mana_cost_range
from util import init_scryfall_data, init_db, init_card_images, init_image_processing, has_internet_connection


DEFAULT_PRINT_FULL = False # print text with art crop by default; False for printing full card images; ignored if only one image type is available


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
    display.display_loading_screen("[1/4]\nDownloading\ncard data...", size=1)
    success = init_scryfall_data()
    display.stop_loading_screen()
    if not success:
        return False

    # Step 2: Create a SQLite database and load card data into it; save image URLs for later downloading
    display.display_loading_screen("[2/4]\nLoading data\ninto db...", size=2)
    success, image_type_data = init_db(image_download_types)
    display.stop_loading_screen()
    if not success:
        return False

    # Step 3: Download card images based on the downloaded card data
    display.display_loading_screen("[3/4]\nDownloading\ncard images...", size=3)
    success = init_card_images(image_type_data)
    display.stop_loading_screen()
    if not success:
        return False

    # Step 4: Process downloaded images (turn into high-contrast black & white versions)
    display.display_loading_screen("[4/4]\nProcessing\ncard images...", size=4)
    success = init_image_processing(image_download_types, printer.device_width)
    display.stop_loading_screen()
    if not success:
        return False
    return True


def main(enabled_image_types: list[str]) -> Literal["shutdown", "restart", "exit"]:
    """Main loop of the program, handling button events and updating the display and printer accordingly.
    This function runs indefinitely until a shutdown or restart is triggered by a button event or an error occurs.
    
    Args:
        enabled_image_types: List of enabled image types determining which print modes are available.
    
    Returns:
        Literal["shutdown", "restart", "exit"]: The exit mode indicating the requested action.
    """
    print("=> Entering main loop. Waiting for button events...")
    display.display_text("~ Momir Vig ~\nLet's begin!", "title")
    rotary_min_value, rotary_max_value = get_mana_cost_range(db)
    skip_values = get_nonexistent_creature_mana_costs(db)
    rotary_value = 0
    current_card = None
    current_face = None
    current_card_info = None
    current_card_image = None
    full_print_mode = DEFAULT_PRINT_FULL if IMAGE_TYPE_FULL in enabled_image_types else False
    new_card_since_mode_switch = False
    button_handler.reset() # reset button state after init
    rotary_encoder_handler.reset()
    rotary_encoder_handler.reset_rotary()
    try:
        while True:
            # handle main button events: single click to display context info, 
            # double click to display/print general info, long press to exit program and trigger shutdown
            button_state = button_handler.get_state()
            if button_state == ButtonState.SINGLE_CLICK:
                # SHOW CARD CONTEXT INFO
                if current_card:
                    gpio.toggle_led_blink(True) # make LED blink while busy
                    current_card_info = get_card_data(current_card, db, current_face)
                    display.display_card_info(current_card_info)
                    gpio.toggle_led_blink(False)
                    gpio.toggle_button_led(True) # turn button LED back on after loading screen
                else:
                    display.display_text("No card printed yet.\nPress the button to print a card.")
                    time.sleep(3)
                display.display_mana_value(rotary_value) # return to default display
                button_handler.reset()
            elif button_state == ButtonState.DOUBLE_CLICK:
                # SWITCH TO PRINT TEXT MODE
                if IMAGE_TYPE_FULL not in enabled_image_types or IMAGE_TYPE_ART not in enabled_image_types:
                    display.display_text("Only one image type is enabled.\nCannot switch print modes.")
                    time.sleep(3)
                    display.display_mana_value(rotary_value) # return to default display
                    button_handler.reset()
                    continue
                full_print_mode = not full_print_mode
                if full_print_mode:
                    display.display_text("Switched to full card print mode.")
                else:
                    display.display_text("Switched to text print mode.")
                time.sleep(2) # give user time to read message
                if current_card:
                    current_card_image = get_card_image_for_mode(current_card, "full" if full_print_mode else "art")
                if not new_card_since_mode_switch: # don't print card again if switching modes back to the same mode as before
                    display.display_mana_value(rotary_value) # return to default display
                    button_handler.reset()
                    continue
                gpio.toggle_led_blink(True) # make LED blink while busy
                display.display_loading_screen("Printing current card in new mode...")
                if full_print_mode: # full card image mode
                    printer.print_card_image(current_card_image)
                else: # text with art crop mode
                    printer.print_card_as_image(current_card_info, current_card_image)
                new_card_since_mode_switch = False
                display.stop_loading_screen()
                gpio.toggle_led_blink(False)
                gpio.toggle_button_led(True) # turn button LED back on after loading screen
                display.display_mana_value(rotary_value) # return to default display
                button_handler.reset()
            elif button_state == ButtonState.LONG_PRESS:
                # SHUTDOWN
                display.display_text("Shutting down...")
                print("=> Shutdown requested. Exiting...")
                time.sleep(2)
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
                display.display_mana_value(rotary_value)
                rotary_encoder_handler.reset_rotary()
            elif rotary_state == RotaryState.LEFT:
                # DECREASE VALUE
                rotary_value -= 1
                if rotary_value in skip_values:
                    rotary_value -= 1
                if rotary_value < rotary_min_value:
                    rotary_value = rotary_max_value
                display.display_mana_value(rotary_value)
                rotary_encoder_handler.reset_rotary()
            
            # handle rotary encoder push button: single click to confirm selected value, 
            # double click currently not used, long press to reset program
            rotary_button_state = rotary_encoder_handler.get_state()
            if rotary_button_state == ButtonState.SINGLE_CLICK:
                # PRINT RANDOM CARD
                gpio.toggle_led_blink(True)
                size = max(1, rotary_value // 2) # thicker loading bars for higher mana costs
                display.display_loading_screen(f"Printing a {rotary_value}\ncost creature!", size=size)
                current_card, current_face = get_random_creature_card(rotary_value, db)
                current_card_info = get_card_data(current_card, db, current_face)
                current_card_image = get_card_image_for_mode(current_card, "full" if full_print_mode else "art")
                if full_print_mode: # print full card image
                    printer.print_card_image(current_card_image)
                else: # print text with art crop
                    printer.print_card_as_image(current_card_info, current_card_image)
                new_card_since_mode_switch = True
                display.stop_loading_screen()
                gpio.toggle_led_blink(False)
                gpio.toggle_button_led(True)
                display.display_mana_value(rotary_value) # return to default display
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.DOUBLE_CLICK:
                # PRINT MOMIR AVATAR CARD
                gpio.toggle_led_blink(True)
                display.display_loading_screen("Printing\nMomir Avatar!")
                current_card = MOMIR_AVATAR_NAME
                current_face = None
                current_card_info = get_card_data(current_card, db, current_face)
                current_card_image = get_card_image_for_mode(current_card, "full" if full_print_mode else "art")
                if full_print_mode: # print full card image
                    printer.print_card_image(current_card_image)
                else: # print text with art crop
                    printer.print_card_as_image(current_card_info, current_card_image)
                new_card_since_mode_switch = True
                display.stop_loading_screen()
                gpio.toggle_led_blink(False)
                gpio.toggle_button_led(True)
                display.display_mana_value(rotary_value) # return to default display
                rotary_encoder_handler.reset()
            elif rotary_button_state == ButtonState.LONG_PRESS:
                # RESTART PROGRAM
                display.display_text("Restarting program...")
                print("=> Restart requested. Restarting...\n")
                time.sleep(2)
                return "restart skipinit"
    except KeyboardInterrupt:
        print("=> Keyboard interrupt received. Exiting...")
    except Exception as e:
        print(f"~> An error occurred: {e}\nRestarting...\n")
        display.display_text("An error occurred.\nRestarting...")
        button_handler.reset()
        time.sleep(3) # wait a moment to allow the user to see the message on the display before restarting
        if button_handler.is_pressed(): # option to instead shut down
            print("Manually shutting down instead...")
            display.display_text("Shutting down instead...")
            time.sleep(2)
            return "shutdown"
        return "restart skipinit"
    return "exit" # just exit the program


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
    parser.add_argument("-t", "--imgtypes", nargs="+", default=_SUPPORTED_IMAGE_TYPES, choices=_SUPPORTED_IMAGE_TYPES, type=str, 
                        help=f"Specify which image types to download and process. Supported types: {_SUPPORTED_IMAGE_TYPES}")
    args = parser.parse_args()
    
    enabled_image_types = args.imgtypes
    if enabled_image_types == [IMAGE_TYPE_FULL]:
        print("=> Using only full card images for printing.")
    elif enabled_image_types == [IMAGE_TYPE_ART]:
        print("=> Using only art crop images for printing.")
    
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
    display.display_text("Momir\nPrinter", "title")
    time.sleep(3)
    
    ### INIT DATA
    
    if not args.skipinit:
        display.display_text("Beginning initialization.")
        time.sleep(2) # wait a moment to give user chance to press button for skipping initialization steps if desired
    
    init_success = True # only false if initialization steps were attempted and then failed
    if args.skipinit or button_handler.is_pressed():
        print("=> Skipping initialization steps...")
        display.display_text("Skipping initialization.")
        time.sleep(2)
    elif has_internet_connection():
        init_success = init(enabled_image_types)
    else:
        print("=> No internet connection detected. Skipping initialization steps...")
        display.display_text("No connection.\nSkipping initialization.")
        time.sleep(2)
    gpio.toggle_led_blink(False) # stop LED blinking after initialization is done
    
    # Restart the program to try initialization again on next run or shutdown if button pressed
    if not init_success: 
        gpio.toggle_led_blink(True, interval=0.2) # blink LED rapidly to indicate initialization failure
        print("=> Initialization failed")
        display.display_text("Initialization failed")
        time.sleep(3)
        if button_handler.is_pressed():
            print("Manually shutting down...")
            display.display_text("Shutting down...")
            exit_mode = "shutdown"
        else:
            print("Restarting...")
            display.display_text("Restarting...")
            exit_mode = "restart"
        time.sleep(2) # wait a moment to allow the user to see the message on the display before restarting or shutting down
    
    ### MAIN LOOP
    
    if init_success: # Only enter main loop if initialization was successful
        gpio.toggle_button_led(True) # turn on LED to indicate that the program is ready for input
        db = DatabaseManager()
        exit_mode = main(enabled_image_types)    
    
    ### CLEANUP

    cleanup()
    if exit_mode == "shutdown": # trigger system shutdown
        subprocess.run(["shutdown"])
    elif exit_mode == "restart": # restart the program
        os.execv(sys.executable, [sys.executable] + sys.argv)
    elif exit_mode == "restart skipinit": # restart the program without initialization
        os.execv(sys.executable, [sys.executable] + sys.argv + ["-s"])
    else: # key interrupt etc
        sys.exit(0)
