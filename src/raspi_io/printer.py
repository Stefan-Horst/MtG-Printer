import time
from functools import lru_cache
from typing import Literal
from PIL import Image, ImageDraw, ImageFont
from escpos.printer import Serial, Dummy

from . import TITLE_FONT_PATH, DETAIL_FONT_PATH, SYMBOL_FONT_PATH, SYMBOL_CODES


CUT_MARGIN = 2 # margin to leave at the bottom of the image for cutting

# Proportions of a real Magic card (63mm x 88mm) used to cap the rendered card length
CARD_ASPECT_W, CARD_ASPECT_H = 63, 88
# Layout constants (in pixels) for the rendered card image
_PAD = 6 # vertical gap between stacked boxes
_BOX_PAD = 5 # padding between a box outline and its text
_OUTLINE = 2 # thickness of the box outlines
_LINE_SPACING = 2 # extra spacing between wrapped oracle text lines
_ART_MAX_FRAC = 0.5 # max fraction of the flexible space the art window may take when there is text
_ART_MIN_H = 60 # minimum height of the art window
_TEXT_MIN_H = 24 # minimum height of the oracle text box
# Font size bounds (max, min) for each element; text is scaled within these to fit its container
_TITLE_CAP, _TITLE_FLOOR = 26, 12
_TYPE_CAP, _TYPE_FLOOR = 19, 10
_ORACLE_CAP, _ORACLE_FLOOR = 17, 9
_PT_CAP, _PT_FLOOR = 22, 12


class PrinterManager:
    """Class to manage interactions with the thermal printer using ESC/POS. 
    Specifically for model QR204 compatible with profile POS-5890."""
    
    def __init__(self):
        self.printer = Serial(devfile="/dev/serial0", baudrate=9600, profile="POS-5890")
        self.dummy_printer = Dummy(profile="POS-5890")
        # Width of the printer in pixels and the possible number of characters per line for normal and narrow font
        self.device_width = self.printer.profile.profile_data["media"]["width"]["pixels"]
        self.base_cols_per_line = self.printer.profile.profile_data["fonts"]["0"]["columns"]
        self.narrow_cols_per_line = self.printer.profile.profile_data["fonts"]["1"]["columns"]

    def is_printer_online(self) -> bool:
        """Check if the printer is online and ready to receive commands."""
        return self.printer.is_online()

    def print_card_image(self, image: Image.Image, feed_after_image: bool = True) -> None:
        """Print a card image on the thermal printer. The image must already be processed 
        to be high-contrast black & white and resized to fit the printer width. 
        Preprocesses the image using a dummy printer for faster actual printing.
        
        Args:
            image: PIL Image object to be printed
            feed_after_image: Whether to feed the printer after printing the image so it can be cut properly
        """
        self.dummy_printer.image(image, impl="bitImageRaster", center=True)
        self.printer._raw(self.dummy_printer.output)
        if feed_after_image:
            time.sleep(2) # wait for the printer buffer to empty
            self.printer.print_and_feed(CUT_MARGIN)

    def print_card_as_image(self, card_data: dict, image: Image.Image) -> None:
        """Print a card by rendering its information into a single PIL image laid out like a real
        Magic card, then sending that image to the printer. Unlike print_card, the card elements are
        drawn as graphics (with the art crop and simple boxes/lines) instead of printed as text.

        Args:
            card_data: Dict containing the card information. Must be standardized so all relevant keys exist.
            image: PIL Image object of the (already black & white) art crop of the card.
        """
        card_image = self._render_card_image(card_data, image)
        self.print_card_image(card_image)

    def _render_card_image(self, card_data: dict, art_image: Image.Image) -> Image.Image:
        """Render the card information and art crop into a single black & white image resembling a
        real Magic card: a boxed title bar (name + mana cost), an art window, a type line bar, an
        oracle text box and a bottom-right power/toughness box. Non-essential visual design is left
        out so the black & white result stays legible. The image width matches the printer width and
        its length is capped to keep real-card proportions; text is scaled to fit its containers. The
        length is only exceeded if the oracle text does not fit even at the smallest font size.

        Args:
            card_data: Dict containing the card information. Must be standardized so all relevant keys exist.
            art_image: PIL Image object of the (already black & white) art crop of the card.
        Returns:
            A 1-bit PIL Image of the rendered card, sized to the printer width.
        """
        name = card_data["name"]
        mana_cost = card_data["mana_cost"]
        type_line = card_data["type_line"]
        oracle_text = card_data["oracle_text"]
        power = card_data["power"]
        toughness = card_data["toughness"]
        has_pt = bool(power or toughness) # not all cards have power/toughness
        pt_text = f"{power} / {toughness}" if has_pt else ""
        has_text = bool(oracle_text)

        width = self.device_width
        scratch = ImageDraw.Draw(Image.new("1", (width, 8), 1)) # for measuring text before the canvas exists
        content_w = width # boxes span the full printer width, no side margins
        text_w = content_w - 2 * (_BOX_PAD + _OUTLINE) # width available for text inside a box
        inpad = _BOX_PAD + _OUTLINE # padding from a box edge to its text

        # Fixed-height boxes: title (name + mana on one line), type line and optional power/toughness
        title_font, name_fit = self._fit_title(scratch, name, mana_cost, text_w, gap=10,
                                               cap=_TITLE_CAP, floor=_TITLE_FLOOR)
        h_title = self._line_height(title_font) + 2 * _BOX_PAD
        type_font, type_fit = self._fit_single_line(scratch, type_line, text_w, cap=_TYPE_CAP, 
                                                    floor=_TYPE_FLOOR, mode="title")
        h_type = self._line_height(type_font) + 2 * _BOX_PAD
        if has_pt:
            pt_font, _ = self._fit_single_line(scratch, pt_text, content_w * 0.45,
                                               cap=_PT_CAP, floor=_PT_FLOOR, mode="title")
            h_pt = self._line_height(pt_font) + 2 * _BOX_PAD
        else:
            pt_font, h_pt = None, 0

        # Divide the remaining vertical space (up to real-card proportions) between the art window and
        # the text box. The art is sized the same whether or not the card has oracle text: a card
        # without oracle text keeps this layout and simply gets an empty text box (no scaled-up art).
        target_h = round(width * CARD_ASPECT_H / CARD_ASPECT_W)
        box_count = 4 + (1 if has_pt else 0) # title, art, type, text, [pt]
        flex = target_h - h_title - h_type - h_pt - (box_count - 1) * _PAD
        art_full_h = round(content_w / (art_image.width / art_image.height)) # art height if spanning full width
        h_art = min(art_full_h, max(_ART_MIN_H, round(flex * _ART_MAX_FRAC)))
        h_art = min(h_art, flex - _TEXT_MIN_H)
        h_text = flex - h_art

        # Scale oracle text to fit its box; only extend the canvas if it overflows the smallest font
        extra = 0
        oracle_font, oracle_lines = None, []
        if has_text:
            oracle_font, oracle_lines = self._fit_wrapped(scratch, oracle_text, text_w, h_text - 2 * _BOX_PAD,
                                                          _ORACLE_CAP, _ORACLE_FLOOR, _LINE_SPACING)
            used = len(oracle_lines) * self._line_height(oracle_font, _LINE_SPACING) + 2 * _BOX_PAD
            extra = max(0, used - h_text) # only grows the canvas if text overflows the smallest font
            h_text += extra

        # Build the canvas (white background); the boxes below fill it edge to edge, without a frame
        total_h = target_h + extra
        img = Image.new("1", (width, total_h), 1)
        draw = ImageDraw.Draw(img)
        x0 = 0
        x1 = width - 1
        y = 0

        # Title bar: name on the left, mana cost on the right
        draw.rectangle([x0, y, x1, y + h_title - 1], outline=0, width=_OUTLINE)
        draw.text((x0 + inpad, y + h_title / 2), name_fit, font=title_font, fill=0, anchor="lm")
        if mana_cost:
            self._draw_rich_text(draw, (x1 - inpad, y + h_title / 2), mana_cost, title_font, fill=0, anchor="rm")
        y += h_title + _PAD

        # Art window: art crop scaled to fit while preserving its aspect ratio, centered (no border)
        scale = min((x1 - x0 + 1) / art_image.width, h_art / art_image.height)
        aw = max(1, round(art_image.width * scale))
        ah = max(1, round(art_image.height * scale))
        art_resized = art_image.convert("L").resize((aw, ah), Image.Resampling.LANCZOS).convert("1")
        img.paste(art_resized, (x0 + ((x1 - x0 + 1) - aw) // 2, y + (h_art - ah) // 2))
        y += h_art + _PAD

        # Type line bar
        draw.rectangle([x0, y, x1, y + h_type - 1], outline=0, width=_OUTLINE)
        draw.text((x0 + inpad, y + h_type / 2), type_fit, font=type_font, fill=0, anchor="lm")
        y += h_type + _PAD

        # Oracle text box (always drawn; empty when the card has no oracle text), text vertically centered
        draw.rectangle([x0, y, x1, y + h_text - 1], outline=0, width=_OUTLINE)
        if has_text:
            step = self._line_height(oracle_font, _LINE_SPACING)
            ty = y + max(inpad, (h_text - len(oracle_lines) * step) // 2)
            for line in oracle_lines:
                self._draw_rich_text(draw, (x0 + inpad, ty), line, oracle_font, fill=0, anchor="la")
                ty += step

        # Power/toughness box: anchored to the bottom-right corner, omitted when the card has none
        if has_pt:
            pt_w = min(draw.textlength(pt_text, font=pt_font) + 2 * inpad, content_w * 0.5)
            pt_top = total_h - h_pt
            draw.rectangle([x1 - pt_w, pt_top, x1, pt_top + h_pt - 1], outline=0, width=_OUTLINE)
            draw.text(((x1 - pt_w + x1) / 2, pt_top + h_pt / 2), pt_text, font=pt_font, fill=0, anchor="mm")

        return img

    def _line_height(self, font: ImageFont.FreeTypeFont, spacing: int = 0) -> int:
        """Return the full line height of a font, optionally including extra line spacing.
        
        Args:
            font: The font to measure
            spacing: Extra line spacing to add (default: 0)
        
        Returns:
            The full line height of the font, in pixels
        """
        ascent, descent = font.getmetrics()
        return ascent + descent + spacing

    def _truncate_to_width(self, draw: ImageDraw.ImageDraw, 
                           text: str,
                           font: ImageFont.FreeTypeFont, 
                           max_width: float) -> str:
        """Truncate text with an ellipsis so it fits within max_width pixels for the given font.
        
        Args:
            draw: ImageDraw object used to measure text
            text: The text to truncate
            font: Font to use for measurement
            max_width: The maximum width in pixels for the text
        
        Returns:
            The truncated text, with an ellipsis appended if truncation occurred. If the text is too short to fit even the ellipsis, returns just the ellipsis.
        """
        if draw.textlength(text, font=font) <= max_width:
            return text
        ellipsis = "..."
        while text and draw.textlength(text + ellipsis, font=font) > max_width:
            text = text[:-1]
        return (text.rstrip() + ellipsis) if text else ellipsis

    def _wrap_paragraphs(self, draw: ImageDraw.ImageDraw, 
                         text: str, 
                         font: ImageFont.FreeTypeFont,
                         max_width: float, 
                         paragraph_gap: bool = False) -> list[str]:
        """Word-wrap text to max_width pixels, preserving explicit newlines as paragraph breaks.
        When paragraph_gap is True, a blank line is inserted between paragraphs to separate them.
        
        Args:
            draw: ImageDraw object used to measure text
            text: The text to wrap
            font: Font to use for wrapping
            max_width: The maximum width in pixels for the wrapped text
            paragraph_gap: Add an empty line after each paragraph if True
        
        Returns:
            List of wrapped lines
        """
        lines = []
        for paragraph in text.replace("\r", "").split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if paragraph_gap and lines:
                lines.append("") # blank line to visually separate paragraphs
            current = ""
            for word in paragraph.split():
                if not current:
                    current = word
                elif self._rich_textlength(draw, current + " " + word, font) <= max_width:
                    current += " " + word
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _fit_title(self, draw: ImageDraw.ImageDraw, 
                   name: str, 
                   mana: str, 
                   max_width: float,
                   gap: int, 
                   cap: int, 
                   floor: int) -> tuple[ImageFont.FreeTypeFont, str]:
        """Find the largest bold font (within cap/floor) that keeps the card name and mana cost
        on a single line. If even the smallest font is too wide, the name is truncated (mana is kept).
        
        Args:
            draw: ImageDraw object used to measure text
            name: The card name
            mana: The mana cost of the card
            max_width: The maximum width of the card in pixels
            gap: The gap between the card name and mana cost in pixels
            cap: The largest font size to try
            floor: The smallest font size to try
        
        Returns:
            tuple: A tuple containing the font and the truncated card name
        """
        for size in range(cap, floor - 1, -1):
            font = self._load_font(size, mode="title")
            name_w = draw.textlength(name, font=font)
            mana_w = self._rich_textlength(draw, mana, font) if mana else 0
            if name_w + (gap if mana else 0) + mana_w <= max_width:
                return font, name
        font = self._load_font(floor, mode="title")
        mana_w = self._rich_textlength(draw, mana, font) if mana else 0
        name = self._truncate_to_width(draw, name, font, max_width - (gap if mana else 0) - mana_w)
        return font, name

    def _fit_single_line(self, draw: ImageDraw.ImageDraw, 
                         text: str, 
                         max_width: float,
                         cap: int, 
                         floor: int, 
                         mode: Literal["title", "detail"] = "title") -> tuple[ImageFont.FreeTypeFont, str]:
        """Find the largest font (within cap/floor) that fits text on one line, truncating if needed.

        Args:
            draw: ImageDraw object used to measure text
            text: The text to fit
            max_width: The maximum width in pixels for the text
            cap: The largest font size to try
            floor: The smallest font size to try
            mode: The font mode ("title" or "detail")
        
        Returns:
            A tuple of (font, fitted_text) where font is the largest font that fits and fitted_text is the text that fits (possibly truncated with an ellipsis).
        """
        for size in range(cap, floor - 1, -1):
            font = self._load_font(size, mode=mode)
            if draw.textlength(text, font=font) <= max_width:
                return font, text
        font = self._load_font(floor, mode=mode)
        return font, self._truncate_to_width(draw, text, font, max_width)

    def _fit_wrapped(self, draw: ImageDraw.ImageDraw, 
                     text: str, 
                     max_width: float, 
                     max_height: float,
                     cap: int, 
                     floor: int, 
                     spacing: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
        """Find the largest font (within cap/floor) whose wrapped text fits within max_width x max_height.
        At each size, paragraphs are separated by a blank line when that still fits, but a larger font is
        preferred over the gaps. Returns the smallest-font wrapping if nothing fits (the caller then
        extends the canvas), never using the gaps in that overflow case.
        
        Args:
            draw: ImageDraw object used to measure text
            text: The text to wrap
            max_width: The maximum width in pixels for the wrapped text
            max_height: The maximum height in pixels for the wrapped text
            cap: The maximum font size to try
            floor: The minimum font size to try
            spacing: Extra spacing between wrapped lines in pixels
        
        Returns:
            A tuple of (font, wrapped_lines) where font is the largest font that fits and wrapped_lines is a list of the wrapped text lines.
        """
        for size in range(cap, floor - 1, -1):
            font = self._load_font(size, mode="detail")
            for paragraph_gap in (True, False): # prefer separating paragraphs, but only if it still fits
                lines = self._wrap_paragraphs(draw, text, font, max_width, paragraph_gap)
                if len(lines) * self._line_height(font, spacing) <= max_height:
                    return font, lines
        font = self._load_font(floor, mode="detail")
        return font, self._wrap_paragraphs(draw, text, font, max_width)

    def _symbol_runs(self, text: str,
                     text_font: ImageFont.FreeTypeFont) -> list[tuple[str, ImageFont.FreeTypeFont]]:
        """Split text into (segment, font) runs, replacing each SYMBOL_CODES key (e.g. "{W}") with its
        glyph from the symbol font, sized to match text_font. Consecutive normal characters are kept
        in one run; text without any symbols yields a single run. Only mana cost and oracle text can
        contain such symbols.

        Args:
            text: The text to split, possibly containing SYMBOL_CODES keys
            text_font: Font used for the normal (non-symbol) segments

        Returns:
            A list of (segment, font) tuples in reading order
        """
        symbol_font = self._load_font(text_font.size, mode="symbol")
        runs, buffer, i = [], [], 0
        while i < len(text):
            end = text.find("}", i) if text[i] == "{" else -1
            key = text[i:end + 1] if end != -1 else ""
            if key in SYMBOL_CODES:
                if buffer:
                    runs.append(("".join(buffer), text_font))
                    buffer = []
                runs.append((SYMBOL_CODES[key], symbol_font))
                i = end + 1
            else:
                buffer.append(text[i])
                i += 1
        if buffer:
            runs.append(("".join(buffer), text_font))
        return runs

    def _rich_textlength(self, draw: ImageDraw.ImageDraw,
                         text: str,
                         text_font: ImageFont.FreeTypeFont) -> float:
        """Return the pixel width of text once SYMBOL_CODES keys are replaced by symbol-font glyphs.

        Args:
            draw: ImageDraw object used to measure text
            text: The text to measure, possibly containing SYMBOL_CODES keys
            text_font: Font used for the normal (non-symbol) segments

        Returns:
            The width of the rendered text in pixels
        """
        return sum(draw.textlength(seg, font=font) for seg, font in self._symbol_runs(text, text_font))

    def _draw_rich_text(self, draw: ImageDraw.ImageDraw,
                        xy: tuple[float, float],
                        text: str,
                        text_font: ImageFont.FreeTypeFont,
                        fill: int,
                        anchor: str) -> None:
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
            total = sum(draw.textlength(seg, font=font) for seg, font in runs)
            x -= total if anchor[0] == "r" else total / 2
        for seg, font in runs:
            draw.text((x, baseline), seg, font=font, fill=fill, anchor="ls")
            x += draw.textlength(seg, font=font)

    @lru_cache(maxsize=None)
    def _load_font(self, size: int,
                   mode: Literal["title", "detail", "symbol"] = "title") -> ImageFont.FreeTypeFont:
        """Load a scalable font at the given size. Results are cached since the same sizes are
        requested repeatedly while fitting text.

        Args:
            size: The font size in points
            mode: The font mode ("title", "detail" or "symbol" for mana/other card symbols)

        Returns:
            A FreeTypeFont object
        """
        font = {"title": TITLE_FONT_PATH, "detail": DETAIL_FONT_PATH, "symbol": SYMBOL_FONT_PATH}[mode]
        return ImageFont.truetype(font, size)

    def close(self) -> None:
        self.printer.close()
