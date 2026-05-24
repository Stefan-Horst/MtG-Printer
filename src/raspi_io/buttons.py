import time
from enum import Enum
from threading import Lock


DOUBLE_CLICK_MAX_INTERVAL = 0.5 # seconds
LONG_PRESS_THRESHOLD = 3 # seconds
ROTARY_THRESHOLD = 0.1 # seconds between rotary encoder events to consider them valid


class ButtonState(Enum):
    IDLE = 0
    SINGLE_CLICK = 1
    DOUBLE_CLICK = 2
    LONG_PRESS = 3

class ButtonHandler:
    """Class to handle button press events with support for single click, double 
    click, and long press detection. Callback functions must be registered with 
    GPIO event detection on both press and release and used together. After 
    detecting an event, the handler is blocked until reset() is called.
    DO NOT read the button state directly, but call get_state()."""
    
    def __init__(self):
        self.last_button_press = 0
        self.last_button_release = 0
        self.state = ButtonState.IDLE
        self.blocked = False
        self.lock = Lock()
    
    def button_callback(self, _, pin_input) -> None:
        """Callback function to handle button events. Must be called with GPIO event detection 
        on both press and release. RPi.GPIO can only handle a single callback per pin and 
        therefore this function acts as a wrapper for the press and release callbacks.
        
        Args:
            pin_input: 0 for press, 1 for release.
        """
        if pin_input == 0:
            self._press_callback(_)
        else:
            self._release_callback(_)
    
    def _press_callback(self, _) -> None:
        """Callback function to handle button press events. Must be called with 
        GPIO event detection on press and used together with release_callback."""
        self.last_button_press = time.time()
    
    def _release_callback(self, _) -> None:
        """Callback function to handle button release events. Must be called with 
        GPIO event detection on release and used together with press_callback."""
        self.last_button_release = time.time()
        with self.lock:
            if self.blocked:
                return
            if self.state == ButtonState.IDLE:
                time_since_press = time.time() - self.last_button_press
                if time_since_press > LONG_PRESS_THRESHOLD:
                    self.state = ButtonState.LONG_PRESS
                    self.blocked = True
                self.state = ButtonState.SINGLE_CLICK # can't block yet because could be double click
            elif (self.state == ButtonState.SINGLE_CLICK 
                  and self.last_button_press - self.last_button_release < DOUBLE_CLICK_MAX_INTERVAL):
                self.state = ButtonState.DOUBLE_CLICK
            self.blocked = True

    def reset(self) -> None:
        """Reset the button handler state. Must be called after handling 
        a detected event to be able to detect the next one."""
        with self.lock:
            self.last_button_press = 0
            self.last_button_release = 0
            self.state = ButtonState.IDLE
            self.blocked = False
    
    def get_state(self) -> ButtonState:
        """Get the current button handler state.
        
        Returns:
            ButtonState: IDLE, SINGLE_CLICK, DOUBLE_CLICK, LONG_PRESS.
        """
        with self.lock:
            if (
                self.state == ButtonState.SINGLE_CLICK 
                and time.time() - self.last_button_release > DOUBLE_CLICK_MAX_INTERVAL
            ):
                self.blocked = True
            if not self.blocked and self.state == ButtonState.SINGLE_CLICK:
                # if single click detected but not blocked yet, return idle until certain if it's double click or not;
                # reset must not be called while waiting for potential double click
                return ButtonState.IDLE
        return self.state


class RotaryState(Enum):
    IDLE = 0
    RIGHT = 1
    LEFT = 2

class RotaryEncoderHandler(ButtonHandler):
    """Class to handle rotary encoder events with support for clockwise and 
    counter-clockwise rotation detection. Callback functions must be registered 
    with GPIO event detection on both rotary pins and used together. After 
    detecting an event, the handler is blocked until reset_rotary() is called. The 
    rotary encoder handler inherits from ButtonHandler to also support its push 
    button. Both states are handled independently and must be reset separately."""
    
    def __init__(self):
        self.last_clk_trigger = 0
        self.last_dt_trigger = 0
        self.rotary_state = RotaryState.IDLE
        self.rotary_blocked = False
        self.lock_re = Lock()
        super().__init__()
    
    def rotary_clk_callback(self, _) -> None:
        """Callback function to handle rotary encoder CLK pin events. 
        Must be called with GPIO event detection and used together with DT."""
        self.last_clk_trigger = time.time()
        with self.lock_re:
            if self.rotary_blocked:
                return
            if time.time() - self.last_dt_trigger < ROTARY_THRESHOLD:
                self.rotary_state = RotaryState.RIGHT
            else:
                self.rotary_state = RotaryState.LEFT
            self.rotary_blocked = True
    
    def rotary_dt_callback(self, _) -> None:
        """Callback function to handle rotary encoder DT pin events. 
        Must be called with GPIO event detection and used together with CLK."""
        self.last_dt_trigger = time.time()
        with self.lock_re:
            if self.rotary_blocked:
                return
            if time.time() - self.last_clk_trigger < ROTARY_THRESHOLD:
                self.rotary_state = RotaryState.LEFT
            else:
                self.rotary_state = RotaryState.RIGHT
            self.rotary_blocked = True
    
    def reset_rotary(self) -> None:
        """Reset the rotary encoder handler state. Must be called after 
        handling a detected event to be able to detect the next one."""
        with self.lock_re:
            self.last_clk_trigger = 0
            self.last_dt_trigger = 0
            self.rotary_state = RotaryState.IDLE
            self.rotary_blocked = False
    
    def get_rotary_state(self) -> RotaryState:
        """Get the current rotary encoder state.
        
        Returns:
            RotaryState: IDLE, RIGHT, LEFT.
        """
        return self.rotary_state
