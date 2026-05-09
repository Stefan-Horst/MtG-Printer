from pathlib import Path
from PIL import Image, ImageOps
from webserver.load_scryfall_data import IMAGE_DIR


BLACK_WHITE_THRESHOLD = 128
PRINTER_IMAGE_DIR = "./images/printer_images"


def process_all_images(image_dir: str = IMAGE_DIR, output_dir: str = PRINTER_IMAGE_DIR):
    """
    Process all images in the specified directory and save the results separately.

    Args:
        image_dir: directory containing the source images
        output_dir: directory for the processed images
    """
    input_path = Path(image_dir)
    for image_file in input_path.iterdir():
        if image_file.is_file() and image_file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            try:
                process_image(image_file.name, image_dir, output_dir)
            except Exception as e:
                print(f"Failed to process image '{image_file.name}': {e}")

def process_image(filename: str, image_dir: str = IMAGE_DIR, output_dir: str = PRINTER_IMAGE_DIR) -> Image:
    """
    Load an image file, turn it into a high-contrast black & white
    version optimized for printing and save the result separately.

    Args:
        filename: name of the image file to process
        image_dir: directory containing the source images
        output_dir: directory for the processed images

    Returns:
        Image: the processed image
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
