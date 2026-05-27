import time

import raspi_io.gpio as gpio
from raspi_io.background_tasks import toggle_led_blink
from raspi_io.buttons import ButtonHandler, ButtonState, RotaryEncoderHandler, RotaryState
from raspi_io.display import DisplayManager
from raspi_io.printer import PrinterManager


ROTARY_MAX_VALUE = 16
ROTARY_MIN_VALUE = 0
SKIP_VALUES = [14]

### CURRENTLY MAINLY TESTING BUTTON & ROTARY FUNCTIONALITY, BUTTON LED + BASIC DISPLAY OUTPUT

print("Starting test...")
gpio.setup_gpio()
toggle_led_blink(True)
display = DisplayManager()
printer = PrinterManager()
button_handler = ButtonHandler()
gpio.add_button_callback(button_handler.button_callback)
rotary_encoder_handler = RotaryEncoderHandler()
gpio.add_rotary_callbacks(rotary_encoder_handler.rotary_callback, 
                          rotary_encoder_handler.button_callback)

display.display_text("Starting test...")
time.sleep(2)
toggle_led_blink(False)
gpio.toggle_button_led(True)
rotary_value = 0
try:
    while True:
        button_state = button_handler.get_state()
        if button_state == ButtonState.SINGLE_CLICK:
            print("Single click detected")
            display.display_text("Single click detected")
            button_handler.reset()
        elif button_state == ButtonState.DOUBLE_CLICK:
            print("Double click detected")
            display.display_text("Double click detected")
            button_handler.reset()
        elif button_state == ButtonState.LONG_PRESS:
            print("Long press detected")
            display.display_text("Long press detected")
            button_handler.reset()
        
        rotary_state = rotary_encoder_handler.get_rotary_state()
        if rotary_state == RotaryState.RIGHT:
            rotary_value += 1
            if rotary_value in SKIP_VALUES:
                rotary_value += 1
            if rotary_value > ROTARY_MAX_VALUE:
                rotary_value = ROTARY_MIN_VALUE
            print(f"Rotary right: {rotary_value}")
            display.display_text(f"Rotary right: {rotary_value}")
            rotary_encoder_handler.reset_rotary()
        elif rotary_state == RotaryState.LEFT:
            rotary_value -= 1
            if rotary_value in SKIP_VALUES:
                rotary_value -= 1
            if rotary_value < ROTARY_MIN_VALUE:
                rotary_value = ROTARY_MAX_VALUE
            print(f"Rotary left: {rotary_value}")
            display.display_text(f"Rotary left: {rotary_value}")
            rotary_encoder_handler.reset_rotary()
        
        rotary_button_state = rotary_encoder_handler.get_state()
        if rotary_button_state == ButtonState.SINGLE_CLICK:
            print("Single click detected on rotary button")
            display.display_text("Single click detected on rotary button")
            rotary_encoder_handler.reset()
        elif rotary_button_state == ButtonState.DOUBLE_CLICK:
            print("Double click detected on rotary button")
            display.display_text("Double click detected on rotary button")
            rotary_encoder_handler.reset()
        elif rotary_button_state == ButtonState.LONG_PRESS:
            print("Long press detected on rotary button")
            display.display_text("Long press detected on rotary button")
            rotary_encoder_handler.reset()
        
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    display.close()
    printer.close()
    gpio.close()