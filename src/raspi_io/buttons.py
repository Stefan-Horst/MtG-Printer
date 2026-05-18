import time
from enum import Enum


DOUBLE_CLICK_THRESHOLD = 0.5 # seconds
LONG_PRESS_THRESHOLD = 3 # seconds

class ButtonState(Enum):
    IDLE = 0
    SINGLE_CLICK = 1
    DOUBLE_CLICK = 2
    LONG_PRESS = 3

class ButtonHandler:
    """Class to handle button press events with support for 
    single click, double click, and long press detection."""
    
    def __init__(self):
        self.last_button_press = 0
        self.state = ButtonState.IDLE
    
    def press_callback(self, channel):
        """Callback function to handle button press events. Must be called with 
        GPIO event detection on press and used together with release_callback."""
        self.last_button_press = time.time()
    
    def release_callback(self, channel):
        """Callback function to handle button release events. Must be called with 
        GPIO event detection on release and used together with press_callback."""
        if self.state == ButtonState.IDLE:
            if time.time() - self.last_button_press < DOUBLE_CLICK_THRESHOLD:
                self.state = ButtonState.SINGLE_CLICK
            elif time.time() - self.last_button_press > LONG_PRESS_THRESHOLD:
                self.state = ButtonState.LONG_PRESS
        elif self.state == ButtonState.SINGLE_CLICK:
            self.state = ButtonState.DOUBLE_CLICK

    def reset(self):
        """Reset the button handler state. Must be called after handling 
        a detected event to be able to detect the next one."""
        self.last_button_press = 0
        self.state = ButtonState.IDLE
