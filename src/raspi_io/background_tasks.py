from threading import Event, Thread
import time

from raspi_io.gpio import toggle_button_led


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
