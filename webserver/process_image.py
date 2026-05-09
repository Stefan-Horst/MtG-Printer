from pathlib import Path
from PIL import Image, ImageOps
from webserver.load_scryfall_data import IMAGE_DIR


BLACK_WHITE_THRESHOLD = 128
PRINTER_IMAGE_DIR = "./printer_images"


def process_image(filename: str, image_dir: str = IMAGE_DIR, output_dir: str = PRINTER_IMAGE_DIR) -> Image:
    """
    Load an image file, turn it into a high-contrast black & white
    version optimized for printing and save the result separately.

    :param input_path: filename or path of the source image
    :param output_path: filename or path for the processed image (optional)
    :return: path of the saved modified image
    """
    input_file = Path(image_dir) / filename
    img = Image.open(input_file)

    # convert to grayscale
    gray = img.convert("L")
    # increase contrast
    gray = ImageOps.autocontrast(gray)
    # threshold to pure black/white
    bw = gray.point(lambda x: 0 if x < BLACK_WHITE_THRESHOLD else 255, "1")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / filename
    bw.save(output_file)
    return bw
