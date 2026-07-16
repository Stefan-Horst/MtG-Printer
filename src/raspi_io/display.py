import time
from threading import Event, Thread
from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
from luma.core.sprite_system import framerate_regulator
from PIL import Image, ImageDraw, ImageFont


class DisplayManager:
    """Class to manage the OLED display connected via I2C. 
    Specifically for SH1106 type monochrome displays."""

    def __init__(self):
        serial = luma_i2c(port=1, address=0x3C)
        self.display = sh1106(serial, width=128, height=64)
        # Thread and event to control loading animation
        self.toggle_loading_animation_thread = None
        self.toggle_loading_animation_event = Event()

    def display_text(self, text: str) -> None:
        """Display text on the OLED display.
        
        Args:
            text: String to display on the OLED screen
        """
        with canvas(self.display) as draw:
            # adjust positioning as needed
            draw.text((10, 25), text, fill="white")

    def display_card_info(self, card_data: dict) -> None:
        """Display card info on the OLED display. Uses scrolling text with automatic line breaks.
        
        Args:
            card_data: Dictionary containing card name, mana cost, type, oracle text, and power/toughness
        """
        name = card_data["name"]
        mana_cost = card_data["mana_cost"]
        type_line = card_data["type_line"]
        oracle_text = card_data["oracle_text"]
        power = card_data["power"]
        toughness = card_data["toughness"]

        font = ImageFont.load_default()
        hyphen_width = font.getlength("-")
        separator = "-" * max(1, int(self.display.width / hyphen_width))
        while font.getlength(separator) > self.display.width:
            separator = separator[:-1]
        separator_width = font.getlength(separator)

        def _right_align_text(text: str, target_width: float) -> str:
            text_width = font.getlength(text)
            if text_width >= target_width:
                return text
            space_count = target_width - text_width
            return " " * space_count + text

        mana_line = _right_align_text(str(mana_cost), separator_width)
        text = (name + "\n" + mana_line + "\n" + separator + "\n" 
                + type_line + "\n" + separator + "\n" 
                + oracle_text.replace("\n", "\n\n")) # add empty line after each paragraph

        power_toughness = None
        if power != "" or toughness != "":
            power_toughness = f"{power}/{toughness}".strip()
            text += "\n" + separator + "\n" + _right_align_text(power_toughness, separator_width)

        self.display_scrolling_text(text.replace("—", "-"), paragraph_gap=False)
    
    def display_scrolling_text(self, text: str, 
                               cycles: int = 1, 
                               start_pause: float = 4.0, 
                               scroll_delay: float = 1.5, 
                               end_pause: float = 2.0,
                               paragraph_gap: bool = True) -> None:
        """Display text with automatic line breaks and vertical scrolling if the text 
        has more lines than the display can show at once based on its width and height.

        Args:
            text: String to display on the OLED screen
            cycles: Number of times to cycle the scrolling effect around the display
            start_pause: Time to pause at the start of scrolling
            scroll_delay: Delay between each scroll step
            end_pause: Time to pause at the end of scrolling
            paragraph_gap: Add an empty line after each paragraph
        """
        font = ImageFont.load_default()
        lines = self._wrap_text(text, font, self.display.width, paragraph_gap)
        if not lines:
            lines = [""]
        line_height = font.getbbox("A")[3] - font.getbbox("A")[1]
        max_lines = max(1, self.display.height // line_height)
        total_lines = len(lines)

        def _draw_page(start_line: int) -> None:
            with canvas(self.display) as draw:
                y = 0
                for line in lines[start_line:start_line + max_lines]:
                    draw.text((0, y), line, font=font, fill="white")
                    y += line_height

        if total_lines <= max_lines:
            _draw_page(0)
            return

        scroll_steps = total_lines - max_lines
        for _ in range(cycles):
            _draw_page(0)
            time.sleep(start_pause)
            for offset in range(1, scroll_steps + 1):
                _draw_page(offset)
                time.sleep(scroll_delay)
            time.sleep(end_pause)

    def _wrap_text(self, raw_text: str, font: ImageFont, width: int, paragraph_gap: bool = True) -> list[str]:
        """Wrap text into lines that fit the display width based on the provided font.
        
        Args:
            raw_text: Text to wrap
            font: Font to use for wrapping
            width: Width of the display in pixels
            paragraph_gap: Add an empty line after each paragraph if True
        Returns:
            List of wrapped lines
        """
        lines = []
        for paragraph in raw_text.replace("\r", "").split("\n"):
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split()
            current_line = words[0]
            for word in words[1:]:
                candidate = f"{current_line} {word}"
                if font.getlength(candidate) <= width:
                    current_line = candidate
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            if paragraph_gap:
                lines.append("") # empty line after each paragraph
        return lines[:-1] if lines[-1] == "" else lines
    
    def display_loading_screen(self, text: str, 
                               size: int = 3, 
                               bar_length: int = 120, 
                               speed: int = 4, 
                               fps: int = 30) -> None:
        """Show an animated loading screen with a rotating bar effect around the text. 
        The animation loop runs in a separate thread until stop_loading_screen() is called.
        
        Args:
            text: String to display in the center of the loading screen
            size: Thickness of the bars in the loading animation in pixels
            bar_length: Length of the rotating bar in pixels
            speed: Speed of the rotating bar animation
            fps: Frames per second for the animation
        """
        width = self.display.width
        height = self.display.height
        regulator = framerate_regulator(fps=fps)

        # Build the path along the outer margin of the display for the rotating bars
        path = []
        for x in range(size, width):
            for i in range(size):
                path.append((x, i))
        for y in range(size, height):
            for i in range(size):
                path.append((width - 1 - i, y))
        for x in range(width - size - 1, -1, -1):
            for i in range(size):
                path.append((x, height - 1 - i))
        for y in range(height - size - 1, -1, -1):
            for i in range(size):
                path.append((i, y))
        path_length = len(path)
        if path_length == 0:
            return

        # Wrap the text to fit inside the bars and calculate positions for centered display
        text_lines = self._wrap_text(text, ImageFont.load_default(), width - 2 * size)
        pos_line_tuples = []
        draw = ImageDraw.Draw(Image.new(self.display.mode, self.display.size)) # simulate canvas
        for num, line in enumerate(text_lines):
            text_width = draw.textbbox((0, 0), line)[2] - draw.textbbox((0, 0), line)[0]
            text_height = draw.textbbox((0, 0), line)[3] - draw.textbbox((0, 0), line)[1]
            text_x = (width - text_width) // 2
            text_y = (height - text_height * len(text_lines)) // 2 + num * text_height
            pos_line_tuples.append(((text_x, text_y), line))
        
        # Animation loop showing rotating bars around text until the event is set
        def _show_animation(event: Event):
            while True:
                for frame in range(path_length / size // speed):
                    with regulator:
                        actual_frame = frame * size * speed
                        start_positions = [
                            actual_frame % path_length, 
                            (actual_frame + path_length // 2) % path_length
                        ]
                        # Generate points for the rotating bars based on the current frame and bar length
                        points = []
                        for start in start_positions:
                            for step in range(bar_length * size):
                                x, y = path[(start + step) % path_length]
                                points.append((x, y))
                        # Draw two opposite white bars moving along the outer margin and static text in the middle 
                        with canvas(self.display) as draw:
                            draw.point(points, fill="white")
                            for pos, line in pos_line_tuples:
                                draw.text(pos, line, fill="white")
                    if event.is_set():
                        return
        
        # Display the loading animation in a separate thread
        if self.toggle_loading_animation_thread: # Ensure only one loading animation thread is running at a time
            self.toggle_loading_animation_event.set()
            self.toggle_loading_animation_thread.join()
        self.toggle_loading_animation_event.clear()
        self.toggle_loading_animation_thread = Thread(target=_show_animation, args=(self.toggle_loading_animation_event,))
        self.toggle_loading_animation_thread.start()
        
    def stop_loading_screen(self) -> None:
        """Stop the loading screen animation and clear the display."""
        self.toggle_loading_animation_event.set()
        self.clear_display()
    
    def clear_display(self) -> None:
        """Clear the OLED display"""
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="white", fill="black")
    
    def close(self) -> None:
        """Clean up the display resources and stop any running animations."""
        if self.toggle_loading_animation_thread:
            self.toggle_loading_animation_event.set()
            self.toggle_loading_animation_thread.join()
        self.display.cleanup()
