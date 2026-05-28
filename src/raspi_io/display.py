from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont
import time


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
    
    def display_scrolling_text(self, text: str, cycles: int = 1, start_pause: float = 3.0, scroll_delay: float = 0.1, end_pause: float = 3.0) -> None:
        """Display text with automatic line breaks and vertical scrolling if the text 
        has more lines than the display can show at once based on its width and height.

        Args:
            text: String to display on the OLED screen
            cycles: Number of times to cycle the scrolling effect around the display
            start_pause: Time to pause at the start of scrolling
            scroll_delay: Delay between each scroll step
            end_pause: Time to pause at the end of scrolling
        """
        width = self.display.width
        height = self.display.height
        font = ImageFont.load_default()

        def wrap_text(raw_text: str) -> list[str]:
            lines: list[str] = []
            for paragraph in raw_text.replace("\r", "").split("\n"):
                if not paragraph:
                    lines.append("")
                    continue
                words = paragraph.split()
                current_line = words[0]
                for word in words[1:]:
                    candidate = f"{current_line} {word}"
                    if font.getsize(candidate)[0] <= width:
                        current_line = candidate
                    else:
                        lines.append(current_line)
                        current_line = word
                lines.append(current_line)
            return lines

        lines = wrap_text(text)
        if not lines:
            lines = [""]

        line_height = font.getsize("A")[1]
        max_lines = max(1, height // line_height)
        total_lines = len(lines)

        def draw_page(start_line: int) -> None:
            with canvas(self.display) as draw:
                y = 0
                for line in lines[start_line:start_line + max_lines]:
                    draw.text((0, y), line, font=font, fill="white")
                    y += line_height

        if total_lines <= max_lines:
            draw_page(0)
            return

        scroll_steps = total_lines - max_lines
        for _ in range(cycles):
            draw_page(0)
            time.sleep(start_pause)
            for offset in range(1, scroll_steps + 1):
                draw_page(offset)
                time.sleep(scroll_delay)
            time.sleep(end_pause)

    def clear_display(self) -> None:
        """Clear the OLED display"""
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="white", fill="black")
    
    def close(self) -> None:
        self.display.cleanup()
