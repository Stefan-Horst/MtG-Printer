### SCRIPT FOR TESTING BUTTON & ROTARY FUNCTIONALITY, BUTTON LED, DISPLAY OUTPUT, AND PRINTING ###
# Pressing the rotary button also tests the printer

import time
from luma.core.render import canvas
from PIL import Image, ImageDraw, ImageFont

import raspi_io.gpio as gpio
from raspi_io.buttons import ButtonHandler, ButtonState, RotaryEncoderHandler, RotaryState
from raspi_io.display import DisplayManager
from raspi_io.printer import PrinterManager, TITLE_FONT_PATH


IDLE_THRESHOLD = 2


print("Starting test...")
gpio.setup_gpio()
gpio.toggle_button_led(True)
display = DisplayManager()
printer = PrinterManager()
button_handler = ButtonHandler()
gpio.add_button_callback(button_handler.button_callback)
rotary_encoder_handler = RotaryEncoderHandler()
gpio.add_rotary_callbacks(rotary_encoder_handler.rotary_callback, 
                          rotary_encoder_handler.button_callback)
display.display_text("Display works!\nPress rotary to print", "detail")

last_event = time.time()
print("Waiting for input...")
try:
    while True:
        button_state = button_handler.get_state()
        if button_state == ButtonState.SINGLE_CLICK:
            print("Single click detected")
            with canvas(display.display) as draw:
                draw.rectangle(display.display.bounding_box, outline="white", fill="black")
                draw.text((display.display.width / 2 - 55, display.display.height / 2 - 5), "Single click detected", fill="white")
            button_handler.reset()
            last_event = time.time()
        elif button_state == ButtonState.DOUBLE_CLICK:
            print("Double click detected")
            display.display_text("Double click detected")
            button_handler.reset()
            last_event = time.time()
        elif button_state == ButtonState.LONG_PRESS:
            print("Long press detected")
            display.display_text("Long press detected")
            button_handler.reset()
            last_event = time.time()
        
        rotary_state = rotary_encoder_handler.get_rotary_state()
        if rotary_state == RotaryState.RIGHT:
            print("Rotary right")
            display.display_text("Rotary right")
            rotary_encoder_handler.reset_rotary()
            last_event = time.time()
        elif rotary_state == RotaryState.LEFT:
            print("Rotary left")
            display.display_text("Rotary left")
            rotary_encoder_handler.reset_rotary()
            last_event = time.time()
        
        rotary_button_state = rotary_encoder_handler.get_state()
        if rotary_button_state == ButtonState.SINGLE_CLICK:
            print("Single click on rotary detected")
            display.display_text("Single click on rotary detected")
            # Test Printer by drawing an image
            img = Image.new("L", (printer.device_width, 100), 255)
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, printer.device_width, 100), fill=255, outline=0, width=5)
            draw.text((printer.device_width / 2 - 130, 25), "Printer works!", fill=0, font=ImageFont.truetype(TITLE_FONT_PATH, 40))
            printer.print_card_image(img)
            rotary_encoder_handler.reset()
            last_event = time.time()
        elif rotary_button_state == ButtonState.DOUBLE_CLICK:
            print("Double click on rotary detected")
            display.display_text("Double click on rotary detected")
            rotary_encoder_handler.reset()
            last_event = time.time()
        elif rotary_button_state == ButtonState.LONG_PRESS:
            print("Long press on rotary detected")
            display.display_text("Long press on rotary detected")
            rotary_encoder_handler.reset()
            last_event = time.time()
        
        if time.time() - last_event > IDLE_THRESHOLD:
            display.display_text("Waiting for input...")
        
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    print("Stopping test...")
    gpio.toggle_button_led(False)
    display.close()
    printer.close()
    gpio.close()
