import time
from enum import Enum
from threading import Lock
from collections.abc import Callable


DOUBLE_CLICK_MAX_INTERVAL = 0.3 # seconds
LONG_PRESS_THRESHOLD = 3 # seconds


class ButtonState(Enum):
    """Enum to represent the current button state."""
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
    
    def button_callback(self, _: int, input_function: Callable[[int], bool], pin_input: int) -> None:
        """Callback function to handle button events. Must be called with GPIO event detection 
        on both press and release. RPi.GPIO can only handle a single callback per pin and 
        therefore this function acts as a wrapper for the press and release callbacks.
        
        Args:
            input_function: Function to get the state of the input pin, usually GPIO.input.
            pin_input: State of the input pin; 0 for press, 1 for release.
        """
        if input_function(pin_input) == 0: # should result in GPIO.input(pin_input) == 0
            self._press_callback(_)
        else:
            self._release_callback(_)
    
    def _press_callback(self, _: int) -> None:
        """Callback function to handle button press events. Must be called with 
        GPIO event detection on press and used together with release_callback."""
        with self.lock:
            self.last_button_press = time.time()
    
    def _release_callback(self, _: int) -> None:
        """Callback function to handle button release events. Must be called with 
        GPIO event detection on release and used together with press_callback."""
        button_release = time.time()
        with self.lock:
            if self.blocked:
                return
            if self.state == ButtonState.IDLE:
                time_pressed = button_release - self.last_button_press
                if time_pressed > LONG_PRESS_THRESHOLD and self.last_button_press != 0: # make sure double click 2nd click wasn't missed
                    self.state = ButtonState.LONG_PRESS
                    self.blocked = True
                else:
                    self.state = ButtonState.SINGLE_CLICK # can't block yet because could be double click
            elif self.state == ButtonState.SINGLE_CLICK:
                self.state = ButtonState.DOUBLE_CLICK
                self.blocked = True
            self.last_button_release = button_release

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
                # if single click detected but not blocked yet, return idle until certain if it's double click or not
                return ButtonState.IDLE
        return self.state


class RotaryState(Enum):
    """Enum to represent the current rotary encoder state."""
    IDLE = 0 # represents unknown or initial state
    RIGHT = 1
    LEFT = 2
    # intermediate states only used internally for rotation direction detection
    HIGH = 3 # represents resting position with both pins HIGH
    LOW = 4  # represents resting position with both pins LOW

class RotaryEncoderHandler(ButtonHandler):
    """Class to handle rotary encoder events with support for clockwise and 
    counter-clockwise rotation detection. Callback functions must be registered 
    with GPIO event detection on both rotary pins and used together. After 
    detecting an event, the handler is blocked until reset_rotary() is called. The 
    rotary encoder handler inherits from ButtonHandler to also support its push 
    button. Both states are handled independently and must be reset separately."""
    
    def __init__(self):
        self.rotary_state = RotaryState.IDLE
        self.rotary_blocked = False
        self.lock_re = Lock()
        super().__init__()
    
    def rotary_callback(self, _: int, input_function: Callable[[int], bool], pin_clk: int, pin_dt: int) -> None:
        """Callback function to handle rotary encoder pin events. 
        Must be called with GPIO event detection and used for both CLK and DT pins.
        
        Args:
            input_function: Function to get the state of the input pin, usually GPIO.input.
            pin_clk: GPIO pin number for the rotary encoder CLK pin.
            pin_dt: GPIO pin number for the rotary encoder DT pin.
        """
        dt = input_function(pin_dt)   # should result in GPIO.input(pin_dt)
        clk = input_function(pin_clk) # should result in GPIO.input(pin_clk)
        with self.lock_re:
            if self.rotary_blocked:
                return
            # the rotary encoder cycles between the following states for each direction: 
            # clockwise:         HIGH -> RIGHT -> LOW -> RIGHT -> HIGH 
            # counter-clockwise: HIGH -> LEFT  -> LOW -> LEFT  -> HIGH 
            # this means the relevant directional state exists twice in the cycle; 
            # both occurences have opposite pin states for dt and clk and must be differentiated based on the last resting state 
            elif (clk == 1 and dt == 0 and self.rotary_state == RotaryState.LOW
                  or clk == 0 and dt == 1 and self.rotary_state == RotaryState.HIGH):
                self.rotary_state = RotaryState.RIGHT
                self.rotary_blocked = True
            elif (clk == 0 and dt == 1 and self.rotary_state == RotaryState.LOW
                  or clk == 1 and dt == 0 and self.rotary_state == RotaryState.HIGH):
                self.rotary_state = RotaryState.LEFT
                self.rotary_blocked = True
            elif clk == 1 and dt == 1:
                self.rotary_state = RotaryState.HIGH
            elif clk == 0 and dt == 0:
                self.rotary_state = RotaryState.LOW
    
    def reset_rotary(self) -> None:
        """Reset the rotary encoder handler state. Must be called after 
        handling a detected event to be able to detect the next one."""
        with self.lock_re:
            self.rotary_state = RotaryState.IDLE
            self.rotary_blocked = False
    
    def get_rotary_state(self) -> RotaryState:
        """Get the current rotary encoder state. 
        Does not return intermediate states as these are not useful.
        
        Returns:
            RotaryState: IDLE, RIGHT, LEFT.
        """
        if not self.rotary_blocked:
            return RotaryState.IDLE
        return self.rotary_state
