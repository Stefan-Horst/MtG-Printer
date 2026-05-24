from collections.abc import Callable
import RPi.GPIO as GPIO

# GPIO Pin Configuration for BCM mode
MODE = GPIO.BOARD
# Rotary encoder
ROTARY_DT = 15
ROTARY_CLK = 16
ROTARY_SW = 18 # Button
# LED Button
BUTTON_PIN = 13
BUTTON_LED = 11

# LGPIO actually implements bouncetime differently: 
# it is the time a signal must be stable before it is detected as a valid event.
BUTTON_BOUNCETIME = 20 # ms, for all buttons
ROTARY_BOUNCETIME = 10 # ms, for rotary encoder


def setup_gpio() -> None:
    """Set up GPIO pins for button and rotary encoder input. Must be called on program start."""
    GPIO.setmode(MODE)
    # Rotary encoder
    GPIO.setup(ROTARY_DT, GPIO.IN)
    GPIO.setup(ROTARY_CLK, GPIO.IN)
    GPIO.setup(ROTARY_SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # LED Button
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_LED, GPIO.OUT)

def add_button_callback(button_callback: Callable[[int], None]) -> None:
    """Add a callback function to handle button events. The callback 
    must be called with GPIO event detection on press and release.
    
    Args:
        button_callback: Callback function to handle button events.
    """
    # add param to callback function to distinguish between press and release events in the same callback
    button_input = GPIO.input(BUTTON_PIN)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.BOTH, callback=lambda _: button_callback(_, button_input), bouncetime=BUTTON_BOUNCETIME)

def add_rotary_callbacks(rotary_clk_callback: Callable[[int], None], 
                         rotary_dt_callback: Callable[[int], None], 
                         button_callback: Callable[[int], None]) -> None:
    """Add callback functions to handle rotary encoder events. The callbacks 
    must be called with GPIO event detection and used together.
    
    Args:
        rotary_clk_callback: Callback function to handle rotary encoder CLK pin events.
        rotary_dt_callback: Callback function to handle rotary encoder DT pin events.
        button_callback: Callback function to handle rotary encoder button events.
    """
    GPIO.add_event_detect(ROTARY_CLK, GPIO.BOTH, callback=rotary_clk_callback, bouncetime=ROTARY_BOUNCETIME)
    GPIO.add_event_detect(ROTARY_DT, GPIO.BOTH, callback=rotary_dt_callback, bouncetime=ROTARY_BOUNCETIME)
    # add param to callback function to distinguish between press and release events in the same callback
    button_input = GPIO.input(ROTARY_SW)
    GPIO.add_event_detect(ROTARY_SW, GPIO.BOTH, callback=lambda _: button_callback(_, button_input), bouncetime=BUTTON_BOUNCETIME)

def toggle_button_led(on: bool = True) -> None:
    """Toggle the button LED on and off.
    
    Args:
        on: If True, turn on the LED. If False, turn off the LED.
    """
    GPIO.output(BUTTON_LED, GPIO.HIGH if on else GPIO.LOW)

def close() -> None:
    """Clean up GPIO settings. Must be called on program exit."""
    GPIO.cleanup()
