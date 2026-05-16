from PIL.Image import Image
from escpos.printer import Serial


DEVICE_WIDTH = 384 # width of the printer in pixels
CUT_MARGIN = 2 # margin to leave at the bottom of the image for cutting


class PrinterManager:
    """Class to manage interactions with the thermal printer using ESC/POS. 
    Specifically for model QR204 compatible with profile POS-5890."""
    
    def __init__(self):
        self.printer = Serial(devfile="/dev/serial0", baudrate=9600, profile="POS-5890")

    def is_printer_online(self) -> bool:
        """Check if the printer is online and ready to receive commands."""
        return self.printer.is_online()

    def print_card_image(self, image: Image) -> None:
        """Print a card image on the thermal printer. The image must already be processed 
        to be high-contrast black & white and resized to fit the printer width.
        
        Args:
            image: PIL Image object to be printed
        """
        self.printer.image(image, impl="bitImageColumn", center=True)
        self.printer.print_and_feed(CUT_MARGIN)
    
    def close(self) -> None:
        self.printer.close()
