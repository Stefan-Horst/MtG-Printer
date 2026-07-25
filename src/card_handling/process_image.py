import asyncio
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
import aiofile

from card_handling.load_scryfall_data import IMAGE_TYPE_ART, IMAGE_TYPE_FULL, _IMAGE_DIR_FULL, make_filename_valid
from . import DATA_PATH


PRINTER_IMAGE_DIR = str(DATA_PATH / "card_images/printer")
IMAGE_EXTENSION = ".png"
MAX_CONCURRENT_TASKS = 100
BLACK_WHITE_THRESHOLD = 128

_PRINTER_IMAGE_DIR_FULL = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_FULL
_PRINTER_IMAGE_DIR_ART = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_ART


def process_all_images(device_width: int, 
                       image_dir: str = _IMAGE_DIR_FULL, 
                       output_dir: str = _PRINTER_IMAGE_DIR_FULL, 
                       skip_existing: bool = True) -> None:
    """
    Process all images in the specified directory and save the results separately.

    Args:
        device_width: Width of the printer in pixels
        image_dir: directory containing the source images
        output_dir: directory for the processed images
        skip_existing: whether to skip processing if the output file already exists
    """
    asyncio.run(_process_all_images(device_width, image_dir, output_dir, skip_existing))

async def _process_all_images(device_width: int, 
                              image_dir: str, 
                              output_dir: str, 
                              skip_existing: bool) -> None:
    """
    Process all images in the specified directory and save the results separately.

    Args:
        device_width: Width of the printer in pixels
        image_dir: directory containing the source images
        output_dir: directory for the processed images
        skip_existing: whether to skip processing if the output file already exists
    """
    input_path = Path(image_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    tasks = [process_image(image_file.name, device_width, image_dir, output_dir, skip_existing, sem=sem) 
             for image_file in input_path.iterdir()
             if image_file.is_file() and image_file.suffix.lower() in [".jpg", ".jpeg", ".png"]]
    await asyncio.gather(*tasks)

async def process_image(file: str, 
                        device_width: int,
                        image_dir: str = _IMAGE_DIR_FULL, 
                        output_dir: str = _PRINTER_IMAGE_DIR_FULL, 
                        skip_existing: bool = True, 
                        return_image: bool = False,
                        sem: asyncio.Semaphore = None) -> Image.Image | None:
    """
    Load an image file, turn it into a high-contrast black & white
    version optimized for printing and save the result separately.

    Args:
        file: name of the image file to process, including extension
        device_width: Width of the printer in pixels
        image_dir: directory containing the source images
        output_dir: directory for the processed images; if None, the image will not be saved
        skip_existing: whether to skip processing if the output file already exists
        return_image: whether to return the processed image; if False, the function returns None
        sem: optional asyncio.Semaphore to limit concurrent processing; if None, no limit is applied

    Returns:
        The processed image if `return_image` is True, otherwise None
    """
    sem = sem or nullcontext() # without sempahore use placeholder context manager that does nothing
    async with sem:
        input_file = Path(image_dir) / file
        filename = input_file.stem
        try:
            img = Image.open(input_file)
            # resize to fit the printer
            ratio = img.size[0] / img.size[1]
            new_height = int(device_width / ratio)
            img = img.resize((device_width, new_height))
            # convert to grayscale
            gray = img.convert("L")
            # increase contrast
            bw = ImageOps.autocontrast(gray, cutoff=5)
        except Exception as e:
            print(f"Failed to process image for {filename}: {e}")
            return None

        if output_dir:
            output_path = Path(output_dir)
            output_file = output_path / f"{filename}{IMAGE_EXTENSION}"
            if not skip_existing or not output_file.exists():
                buffer = BytesIO()
                bw.save(buffer, format=IMAGE_EXTENSION[1:])
                try:
                    async with aiofile.async_open(output_file, "wb") as f:
                        await f.write(buffer.getbuffer())
                except Exception:
                    Path(output_file).unlink(missing_ok=True)
                    print(f"Failed to save image for {filename}. Trying again...")
                    try:
                        async with aiofile.async_open(output_file, "wb") as f:
                            await f.write(buffer.getbuffer())
                    except Exception as e:
                        Path(output_file).unlink(missing_ok=True)
                        print(f"Failed to save image for {filename}: {e}")

        if return_image:
            return bw
    return None

def get_card_image_for_mode(card_name: str, mode: str) -> Image.Image:
    """Get the card printer image for the specified mode (full or art) from the database.
    
    Args:
        card_name: The name of the card to query.
        mode: The mode for which to get the card image ("full" or "art").
    Returns:
        Image.Image: A PIL Image object representing the card printer image.
    """
    img_name = make_filename_valid(card_name)
    if mode == "full":
        return Image.open(f"{_PRINTER_IMAGE_DIR_FULL}/{img_name}")
    elif mode == "art":
        return Image.open(f"{_PRINTER_IMAGE_DIR_ART}/{img_name}")
    else:
        raise ValueError("Invalid mode. Must be 'full' or 'art'.")
