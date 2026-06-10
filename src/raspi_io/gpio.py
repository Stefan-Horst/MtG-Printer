import time
from threading import Event, Thread
from collections.abc import Callable
import RPi.GPIO as GPIO

# GPIO Pin Configuration for BCM mode
MODE = GPIO.BOARD
# Rotary encoder
ROTARY_CLK = 16
ROTARY_DT = 18
ROTARY_SW = 15 # Button
# LED Button
BUTTON_PIN = 13
BUTTON_LED = 11

# LGPIO actually implements bouncetime differently: 
# it is the time a signal must be stable before it is detected as a valid event.
BUTTON_BOUNCETIME = 10 # ms, for all buttons
ROTARY_BOUNCETIME = 5  # ms, for rotary encoder


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

def add_button_callback(button_callback: Callable[[int, Callable[[int], bool], int], None]) -> None:
    """Add a callback function to handle button events. The callback 
    must be called with GPIO event detection on press and release.
    
    Args:
        button_callback: Callback function to handle button events.
    """
    # add param to callback function to distinguish between press and release events in the same callback
    button_callback_wrapper = lambda _: button_callback(_, GPIO.input, BUTTON_PIN)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.BOTH, callback=button_callback_wrapper, bouncetime=BUTTON_BOUNCETIME)

def add_rotary_callbacks(rotary_callback: Callable[[int, Callable[[int], bool], int, int], None], 
                         button_callback: Callable[[int, Callable[[int], bool], int], None]) -> None:
    """Add callback functions to handle rotary encoder events. The callbacks 
    must be called with GPIO event detection on both CLK and DT pins.
    
    Args:
        rotary_callback: Callback function to handle rotary encoder CLK and DT pin events.
        button_callback: Callback function to handle rotary encoder button events.
    """
    # add params to callback function to enable accessing both pin inputs for rotation direction detection
    rotary_callback_wrapper = lambda _: rotary_callback(_, GPIO.input, ROTARY_CLK, ROTARY_DT)
    # need to use GPIO.BOTH as the rotary encoder cycles between HIGH and LOW resting positions during rotation
    GPIO.add_event_detect(ROTARY_CLK, GPIO.BOTH, callback=rotary_callback_wrapper, bouncetime=ROTARY_BOUNCETIME)
    GPIO.add_event_detect(ROTARY_DT, GPIO.BOTH, callback=rotary_callback_wrapper, bouncetime=ROTARY_BOUNCETIME)
    # add param to callback function to distinguish between press and release events in the same callback
    button_callback_wrapper = lambda _: button_callback(_, GPIO.input, ROTARY_SW)
    GPIO.add_event_detect(ROTARY_SW, GPIO.BOTH, callback=button_callback_wrapper, bouncetime=BUTTON_BOUNCETIME)

def toggle_button_led(on: bool = True) -> None:
    """Toggle the button LED on and off.
    
    Args:
        on: If True, turn on the LED. If False, turn off the LED.
    """
    GPIO.output(BUTTON_LED, GPIO.HIGH if on else GPIO.LOW)

toggle_led_event = Event()

def toggle_led_blink(on: bool = True, interval: float = 0.5) -> None:
    """Toggle the button LED on and off in a blinking pattern in the background 
    using a separate thread. Must be called to start or stop the blinking pattern.
    
    Args:
        on: If True, start the blinking pattern. If False, stop the blinking pattern.
        interval: The time interval between on and off in seconds during blinking.
    """
    def _blink(event: Event):
        while not event.is_set():
            toggle_button_led(True)
            time.sleep(interval)
            toggle_button_led(False)
            time.sleep(interval)
    if on:
        toggle_led_event.clear()
        Thread(target=_blink, args=(toggle_led_event,)).start()
    else:
        toggle_led_event.set()

def close() -> None:
    """Clean up GPIO settings. Must be called on program exit."""
    GPIO.cleanup()
