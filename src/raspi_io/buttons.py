import time
from enum import Enum


DOUBLE_CLICK_THRESHOLD = 0.5 # seconds
LONG_PRESS_THRESHOLD = 3 # seconds
ROTARY_THRESHOLD = 0.1 # seconds between rotary encoder events to consider them valid


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
    
    def press_callback(self, channel) -> None:
        """Callback function to handle button press events. Must be called with 
        GPIO event detection on press and used together with release_callback."""
        self.last_button_press = time.time()
    
    def release_callback(self, channel) -> None:
        """Callback function to handle button release events. Must be called with 
        GPIO event detection on release and used together with press_callback."""
        if self.state == ButtonState.IDLE:
            if time.time() - self.last_button_press < DOUBLE_CLICK_THRESHOLD:
                self.state = ButtonState.SINGLE_CLICK
            elif time.time() - self.last_button_press > LONG_PRESS_THRESHOLD:
                self.state = ButtonState.LONG_PRESS
        elif self.state == ButtonState.SINGLE_CLICK:
            self.state = ButtonState.DOUBLE_CLICK

    def reset(self) -> None:
        """Reset the button handler state. Must be called after handling 
        a detected event to be able to detect the next one."""
        self.last_button_press = 0
        self.state = ButtonState.IDLE
    
    def get_state(self) -> ButtonState:
        """Get the current button handler state.
        
        Returns:
            ButtonState: IDLE, SINGLE_CLICK, DOUBLE_CLICK, LONG_PRESS.
        """
        return self.state


class RotaryState(Enum):
    IDLE = 0
    RIGHT = 1
    LEFT = 2

class RotaryEncoderHandler(ButtonHandler):
    """Class to handle rotary encoder events with support for clockwise 
    and counter-clockwise rotation detection. After detecting an event, 
    the handler is blocked until reset_rotary() is called to prevent 
    multiple detections from a single rotation. The rotary encoder 
    inherits from ButtonHandler to also support its push button. Both 
    states are handled independently and must be reset separately."""
    
    def __init__(self):
        self.last_clk_trigger = 0
        self.last_dt_trigger = 0
        self.rotary_state = RotaryState.IDLE
        self.blocked = False
    
    def rotary_clk_callback(self, channel) -> None:
        """Callback function to handle rotary encoder CLK pin events. 
        Must be called with GPIO event detection and used together with DT."""
        self.last_clk_trigger = time.time()
        if not self.blocked:
            if time.time() - self.last_dt_trigger < ROTARY_THRESHOLD:
                self.rotary_state = RotaryState.RIGHT
            else:
                self.rotary_state = RotaryState.LEFT
            self.blocked = True
    
    def rotary_dt_callback(self, channel) -> None:
        """Callback function to handle rotary encoder DT pin events. 
        Must be called with GPIO event detection and used together with CLK."""
        self.last_dt_trigger = time.time()
        if not self.blocked:
            if time.time() - self.last_clk_trigger < ROTARY_THRESHOLD:
                self.rotary_state = RotaryState.LEFT
            else:
                self.rotary_state = RotaryState.RIGHT
            self.blocked = True
    
    def reset_rotary(self) -> None:
        """Reset the rotary encoder handler state. Must be called after 
        handling a detected event to be able to detect the next one."""
        self.last_clk_trigger = 0
        self.last_dt_trigger = 0
        self.rotary_state = RotaryState.IDLE
        self.blocked = False
    
    def get_rotary_state(self) -> RotaryState:
        """Get the current rotary encoder state.
        
        Returns:
            RotaryState: IDLE, RIGHT, LEFT.
        """
        return self.rotary_state
