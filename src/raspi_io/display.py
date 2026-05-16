from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import sh1106
from luma.core.render import canvas


class DisplayManager:
    """Class to manage the OLED display connected via I2C. 
    Specifically for SH1106 type monochrome displays."""

    def __init__(self):
        serial = luma_i2c(port=1, address=0x3C)
        self.display = sh1106(serial, width=128, height=64)

    def display_text(self, text: str) -> None:
        """Display text on the OLED display.
        
        Args:
            text: string to display on the OLED screen
        """
        with canvas(self.display) as draw:
            # adjust positioning as needed
            draw.text((10, 25), text, fill="white")
    
    def clear_display(self) -> None:
        """Clear the OLED display"""
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="white", fill="black")
    
    def close(self) -> None:
        self.display.cleanup()
