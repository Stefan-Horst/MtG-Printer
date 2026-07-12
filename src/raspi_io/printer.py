from PIL.Image import Image
from escpos.printer import Serial, Dummy


CUT_MARGIN = 3 # margin to leave at the bottom of the image for cutting


class PrinterManager:
    """Class to manage interactions with the thermal printer using ESC/POS. 
    Specifically for model QR204 compatible with profile POS-5890."""
    
    def __init__(self):
        self.printer = Serial(devfile="/dev/serial0", baudrate=9600, profile="POS-5890")
        self.dummy_printer = Dummy(profile="POS-5890")
        # Width of the printer in pixels and the possible number of characters per line for normal and narrow font
        self.device_width = self.printer.profile["media"]["width"]["pixels"]
        self.base_cols_per_line = self.printer.profile["fonts"]["0"]["columns"]
        self.narrow_cols_per_line = self.printer.profile["fonts"]["1"]["columns"]

    def is_printer_online(self) -> bool:
        """Check if the printer is online and ready to receive commands."""
        return self.printer.is_online()

    def print_card_image(self, image: Image, feed_after_image: bool = True) -> None:
        """Print a card image on the thermal printer. The image must already be processed 
        to be high-contrast black & white and resized to fit the printer width. 
        Preprocesses the image using a dummy printer for faster actual printing.
        
        Args:
            image: PIL Image object to be printed
            feed_after_image: Whether to feed the printer after printing the image so it can be cut properly
        """
        self.dummy_printer.image(image, impl="bitImageColumn", center=True)
        self.printer._raw(self.dummy_printer.output)
        if feed_after_image:
            self.printer.print_and_feed(CUT_MARGIN)
    
    def close(self) -> None:
        self.printer.close()
