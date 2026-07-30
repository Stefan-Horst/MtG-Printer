import time
from threading import Event, Thread
from typing import Literal
from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
from luma.core.sprite_system import framerate_regulator
from PIL import Image, ImageDraw, ImageFont

from . import TITLE_FONT_PATH, DETAIL_FONT_PATH, SYMBOL_FONT_PATH, SYMBOL_CODES


VERTICAL_LINE_SPACING = 4 # spacing between vertical lines for detail font


class DisplayManager:
    """Class to manage the OLED display connected via I2C. 
    Specifically for SH1106 type monochrome displays."""

    def __init__(self):
        serial = luma_i2c(port=1, address=0x3C)
        self.display = sh1106(serial, width=128, height=64)
        self.title_font = ImageFont.truetype(TITLE_FONT_PATH, 20)
        self.detail_font = ImageFont.truetype(DETAIL_FONT_PATH, 12)
        self.symbol_fonts = {} # symbol fonts cached by size, matching the text font whose glyphs they replace
        # Thread and event to control loading animation
        self.toggle_loading_animation_thread = None
        self.toggle_loading_animation_event = Event()

    def display_text(self, text: str, mode: Literal["title", "detail"] = "detail") -> None:
        """Display text on the OLED display. Uses automatic line breaks and centers the text on the display.
        
        Args:
            text: String to display on the OLED screen
            mode: Font mode to use for displaying the text ("title" or "detail")
        """
        font = self.title_font if mode == "title" else self.detail_font
        text_lines = self._wrap_text(text, font, self.display.width, paragraph_gap=False)
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        start_y = (self.display.height - line_height * len(text_lines)) // 2
        with canvas(self.display) as draw:
            for num, line in enumerate(text_lines):
                self._draw_rich_text(draw, (self.display.width // 2, start_y + num * line_height),
                                     line, font, fill="white", anchor="ma")

    def display_mana_value(self, mana_value: int) -> None:
        """Display a mana value on the OLED display with custom font size and formatting.
        
        Args:
            mana_cost: Integer mana cost to display
        """
        line1 = "Mana Value"
        x1 = (self.display.width - self.title_font.getlength(line1)) // 2
        y1 = (self.display.height - self.title_font.getbbox(line1)[3]) // 2 - self.title_font.getbbox(line1)[3] - 5
        line2 = str(mana_value)
        title_font_large = ImageFont.truetype(TITLE_FONT_PATH, 40)
        x2 = (self.display.width - title_font_large.getlength(line2)) // 2
        y2 = (self.display.height - title_font_large.getbbox(line2)[3]) // 2 + title_font_large.getbbox(line1)[3] - 30
        with canvas(self.display) as draw:
            draw.text((x1, y1), line1, font=self.title_font, fill="white")
            draw.text((x2, y2), line2, font=title_font_large, fill="white")

    def display_card_info(self, card_data: dict) -> None:
        """Display card info on the OLED display as scrolling text. The card name and mana cost share
        the first line (name on the left, mana cost on the right) when they fit; otherwise the mana
        cost drops to its own line. The type line and oracle text are left-aligned and the
        power/toughness is right-aligned. Mana symbols are rendered with the symbol font, and the
        alignment accounts for their glyph widths.

        Args:
            card_data: Dict containing the card information. Must be standardized so all relevant keys exist.
        """
        name = card_data["name"].replace("—", "-")
        mana_cost = card_data["mana_cost"]
        type_line = card_data["type_line"].replace("—", "-")
        oracle_text = card_data["oracle_text"].replace("—", "-")
        power = card_data["power"]
        toughness = card_data["toughness"]

        # Separator line of hyphens spanning close to the full display width
        separator = "-" * max(1, int(self.display.width / self.detail_font.getlength("-")))
        while self.detail_font.getlength(separator) > self.display.width:
            separator = separator[:-1]

        # Rows to scroll as (left_text, right_text)
        gap = self.detail_font.getlength(" " * 2) # minimum gap between name and mana cost
        name_w = self._rich_textlength(name, self.detail_font)
        mana_w = self._rich_textlength(mana_cost, self.detail_font)
        if mana_cost and name_w + gap + mana_w <= self.display.width:
            rows = [(name, mana_cost)]
        elif mana_cost:
            rows = [(name, ""), ("", mana_cost)]
        else:
            rows = [(name, "")]
        rows += [(separator, ""), (type_line, ""), (separator, "")]
        oracle_paragraphs = [paragraph for paragraph in oracle_text.split("\n") if paragraph]
        for i, paragraph in enumerate(oracle_paragraphs):
            if i > 0:
                rows.append(("", "")) # blank line between oracle paragraphs
            rows.append((paragraph, ""))
        if power or toughness:
            rows += [(separator, ""), ("", f"{power} / {toughness}")]

        self.display_scrolling_text(rows)
    
    def display_scrolling_text(self, rows: list[tuple[str, str]],
                               cycles: int = 1,
                               start_pause: float = 4.0,
                               scroll_delay: float = 1.0,
                               end_pause: float = 2.0) -> None:
        """Display rows of text with automatic line breaks and vertical scrolling if they don't all
        fit on the display at once. Each row is a (left_text, right_text) pair drawn on one line with
        the left part left-aligned and the right part right-aligned; long left-only rows are wrapped to
        the display width. Mana symbols are rendered with the symbol font, and the right alignment
        accounts for the resulting glyph widths.

        Args:
            rows: List of (left_text, right_text) pairs to display on each line
            cycles: Number of times to cycle the scrolling effect around the display
            start_pause: Time to pause at the start of scrolling
            scroll_delay: Delay between each scroll step
            end_pause: Time to pause at the end of scrolling
        """
        lines = self._wrap_rows(rows)
        lines.append(("", "")) # add an empty line at the end to avoid cutting off the last line
        line_advance = self.detail_font.getbbox("A")[3] - self.detail_font.getbbox("A")[1] + VERTICAL_LINE_SPACING
        max_lines = max(1, self.display.height // line_advance)
        total_lines = len(lines)

        if total_lines <= max_lines:
            self._draw_scroll_page(lines, 0, max_lines, line_advance)
            return

        scroll_steps = total_lines - max_lines
        for _ in range(cycles):
            self._draw_scroll_page(lines, 0, max_lines, line_advance)
            time.sleep(start_pause)
            for offset in range(1, scroll_steps + 1):
                self._draw_scroll_page(lines, offset, max_lines, line_advance)
                time.sleep(scroll_delay)
            time.sleep(end_pause)

    def _wrap_rows(self, rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Wrap each (left, right) row to the display width, returning the resulting display lines.
        Long left-only rows are split across several lines; combined and right-only rows stay on one.

        Args:
            rows: List of (left_text, right_text) rows to wrap
        Returns:
            List of (left_text, right_text) lines that each fit the display width
        """
        lines = []
        for left, right in rows:
            if left and not right:
                lines += [(line, "") for line
                          in self._wrap_text(left, self.detail_font, self.display.width, paragraph_gap=False)]
            else:
                lines.append((left, right))
        return lines

    def _draw_scroll_page(self, lines: list[tuple[str, str]],
                          start_line: int, count: int, line_advance: int) -> None:
        """Draw up to `count` display lines starting at `start_line`, with each line's left part
        left-aligned and its right part right-aligned.

        Args:
            lines: The full list of (left_text, right_text) display lines
            start_line: Index of the first line to draw
            count: Maximum number of lines to draw on the page
            line_advance: Vertical distance in pixels between consecutive lines
        """
        with canvas(self.display) as draw:
            y = 0
            for left, right in lines[start_line:start_line + count]:
                if left:
                    self._draw_rich_text(draw, (0, y), left, self.detail_font, fill="white", anchor="la")
                if right:
                    self._draw_rich_text(draw, (self.display.width, y), right, self.detail_font, fill="white", anchor="ra")
                y += line_advance

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
                if self._rich_textlength(candidate, font) <= width:
                    current_line = candidate
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            if paragraph_gap:
                lines.append("") # empty line after each paragraph
        return lines[:-1] if lines[-1] == "" else lines

    def _symbol_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Return the symbol font at the given size, cached since the same sizes recur.

        Args:
            size: The font size in points (matching the text font the symbols appear in)
        Returns:
            A FreeTypeFont object for the symbol font
        """
        font = self.symbol_fonts.get(size)
        if font is None:
            font = ImageFont.truetype(SYMBOL_FONT_PATH, size)
            self.symbol_fonts[size] = font
        return font

    def _symbol_runs(self, text: str,
                     text_font: ImageFont.FreeTypeFont) -> list[tuple[str, ImageFont.FreeTypeFont]]:
        """Split text into (segment, font) runs, replacing each SYMBOL_CODES key (e.g. "{W}") with its
        glyph from the symbol font, sized to match text_font. Consecutive normal characters are kept in
        one run; text without any symbols yields a single run. Only mana cost and oracle text can
        contain such symbols. A "{...}" token that is not a known symbol is shown with round braces
        instead of curly ones.

        Args:
            text: The text to split, possibly containing SYMBOL_CODES keys
            text_font: Font used for the normal (non-symbol) segments
        Returns:
            A list of (segment, font) tuples in reading order
        """
        symbol_font = self._symbol_font(text_font.size)
        runs, buffer, i = [], [], 0
        while i < len(text):
            end = text.find("}", i) if text[i] == "{" else -1
            key = text[i:end + 1] if end != -1 else ""
            if key in SYMBOL_CODES: # known symbol: replace the key with its glyph in the symbol font
                if buffer:
                    runs.append(("".join(buffer), text_font))
                    buffer = []
                runs.append((SYMBOL_CODES[key], symbol_font))
                i = end + 1
            elif end != -1: # a {...} token without a known symbol: show it with round braces instead
                buffer.append("(" + text[i + 1:end] + ")")
                i = end + 1
            else:
                buffer.append(text[i])
                i += 1
        if buffer:
            runs.append(("".join(buffer), text_font))
        return runs

    def _rich_textlength(self, text: str, text_font: ImageFont.FreeTypeFont) -> float:
        """Return the pixel width of text once SYMBOL_CODES keys are replaced by symbol-font glyphs.

        Args:
            text: The text to measure, possibly containing SYMBOL_CODES keys
            text_font: Font used for the normal (non-symbol) segments
        Returns:
            The width of the rendered text in pixels
        """
        return sum(font.getlength(seg) for seg, font in self._symbol_runs(text, text_font))

    def _draw_rich_text(self, draw: ImageDraw.ImageDraw,
                        xy: tuple[float, float],
                        text: str,
                        text_font: ImageFont.FreeTypeFont,
                        fill: str,
                        anchor: str = "la") -> None:
        """Draw text with SYMBOL_CODES keys replaced by symbol-font glyphs, keeping every run on a
        shared baseline so symbols align with the surrounding text. Horizontal alignment (anchor[0])
        may be "l", "m" or "r"; vertical alignment (anchor[1]) may be "a" (top), "m" (middle) or "s".

        Args:
            draw: ImageDraw object used to draw the text
            xy: The (x, y) anchor position
            text: The text to draw, possibly containing SYMBOL_CODES keys
            text_font: Font used for the normal (non-symbol) segments
            fill: The color to draw the text with
            anchor: A PIL two-character anchor string
        """
        x, y = xy
        ascent, descent = text_font.getmetrics()
        if anchor[1] == "a": # top
            baseline = y + ascent
        elif anchor[1] == "m": # middle
            baseline = y + (ascent - descent) / 2
        else: # "s" baseline
            baseline = y
        runs = self._symbol_runs(text, text_font)
        if anchor[0] != "l": # shift start so the whole run block is right- or center-aligned
            total = sum(font.getlength(seg) for seg, font in runs)
            x -= total if anchor[0] == "r" else total / 2
        for seg, font in runs:
            draw.text((x, baseline), seg, font=font, fill=fill, anchor="ls")
            x += font.getlength(seg)
    
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
        text_lines = self._wrap_text(text, self.detail_font, width - 2 * size)
        pos_line_tuples = []
        draw = ImageDraw.Draw(Image.new(self.display.mode, self.display.size)) # simulate canvas
        for num, line in enumerate(text_lines):
            text_width = draw.textbbox((0, 0), line, font=self.detail_font)[2] - draw.textbbox((0, 0), line, font=self.detail_font)[0]
            text_height = draw.textbbox((0, 0), line, font=self.detail_font)[3] - draw.textbbox((0, 0), line, font=self.detail_font)[1]
            text_x = (width - text_width) // 2
            text_y = (height - text_height * len(text_lines)) // 2 + num * text_height
            pos_line_tuples.append(((text_x, text_y), line))
        
        # Animation loop showing rotating bars around text until the event is set
        def _show_animation(event: Event):
            while True:
                for frame in range(path_length // size // speed):
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
                                draw.text(pos, line, font=self.detail_font, fill="white")
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
