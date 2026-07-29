import os
import asyncio
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
import aiofile

from card_handling.load_scryfall_data import IMAGE_TYPE_ART, IMAGE_TYPE_FULL, _IMAGE_DIR_FULL, make_filename_valid
from . import DATA_PATH


PRINTER_IMAGE_DIR = str(DATA_PATH / "card_images/printer")
IMAGE_EXTENSION = ".png"
BATCH_SIZE = 1000
MAX_CONCURRENT_TASKS = 100

_PRINTER_IMAGE_DIR_FULL = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_FULL
_PRINTER_IMAGE_DIR_ART = PRINTER_IMAGE_DIR+"/"+IMAGE_TYPE_ART


def process_all_images(device_width: int, 
                       image_dir: str = _IMAGE_DIR_FULL, 
                       output_dir: str = _PRINTER_IMAGE_DIR_FULL, 
                       batch_size: int = BATCH_SIZE,
                       skip_existing: bool = True) -> None:
    """
    Process all images in the specified directory in batches and save the results separately.

    Args:
        device_width: Width of the printer in pixels
        image_dir: directory containing the source images
        output_dir: directory for the processed images
        batch_size: Number of images to process at once
        skip_existing: whether to skip processing if the output file already exists
    """
    asyncio.run(_process_all_images(device_width, image_dir, output_dir, batch_size, skip_existing))

async def _process_all_images(device_width: int, 
                              image_dir: str, 
                              output_dir: str, 
                              batch_size: int,
                              skip_existing: bool) -> None:
    """
    Process all images in the specified directory in batches and save the results separately.

    Args:
        device_width: Width of the printer in pixels
        image_dir: directory containing the source images
        output_dir: directory for the processed images
        batch_size: Number of images to process at once
        skip_existing: whether to skip processing if the output file already exists
    """
    input_path = Path(image_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    image_files = input_path.iterdir()
    if skip_existing:
        existing_images = {file.stem for file in output_path.glob("*" + IMAGE_EXTENSION)}
        image_files = [file for file in image_files if file.stem not in existing_images]
        print(f"Skipping {len(existing_images)} existing images. Processing {len(image_files)} new images...")
    
    def _get_corrupt_files(chunk: list[Path], output_dir: Path) -> list[Path]:
        """Check if the output files in a chunk are corrupted. Returns a list of corrupted files."""
        out = lambda f: output_dir / f"{f.stem}{IMAGE_EXTENSION}"
        return [f for f in chunk if not out(f).exists() or out(f).stat().st_size == 0]
    
    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    batch_amount = (len(image_files) + batch_size - 1) // batch_size
    for i in range(0, len(image_files), batch_size):
        print(f"Processing image batch {i // batch_size + 1}/{batch_amount}...")
        chunk = image_files[i:i+batch_size]
        tasks = [process_image(image_file.name, device_width, image_dir, output_dir, sem=sem) 
                 for image_file in chunk]
        await asyncio.gather(*tasks)
        fails = _get_corrupt_files(chunk, output_dir)
        if fails:
            print(f"Failed to process {len(fails)} images. Trying again...")
            tasks = [process_image(f.name, device_width, image_dir, output_dir, sem=sem) for f in fails]
            await asyncio.gather(*tasks)
            fails = _get_corrupt_files(chunk, output_dir)
            if fails:
                print(f"~> Failed to process {len(fails)} images again. Skipping...")
                for f in fails: # delete corrupted images
                    (Path(output_dir) / f"{f.stem}{IMAGE_EXTENSION}").unlink(missing_ok=True)

async def process_image(file: str, 
                        device_width: int,
                        image_dir: str = _IMAGE_DIR_FULL, 
                        output_dir: str = _PRINTER_IMAGE_DIR_FULL, 
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
        return_image: whether to return the processed image; if False, the function returns None
        sem: optional asyncio.Semaphore to limit concurrent processing; if None, no limit is applied

    Returns:
        The processed image if `return_image` is True, otherwise None
    """
    async def _save_image(tmp_file: Path, output_file: Path, data: bytes) -> None:
        """Save the image data to the output file using an intermediate temporary file."""
        async with aiofile.async_open(tmp_file, "wb") as f:
            await f.write(data)
        if tmp_file.stat().st_size != len(data):
            raise IOError(f"short write: {tmp_file.stat().st_size}/{len(data)} bytes")
        os.replace(tmp_file, output_file)
    
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
            buffer = BytesIO()
            bw.save(buffer, format=IMAGE_EXTENSION[1:])
            data = buffer.getvalue()
            tmp_file = output_file.with_suffix(output_file.suffix + ".tmp")
            try:
                _save_image(tmp_file, output_file, data)
            except Exception:
                Path(tmp_file).unlink(missing_ok=True)
                print(f"Failed to save image for {filename}. Trying again...")
                try:
                    _save_image(tmp_file, output_file, data)
                except Exception as e:
                    Path(output_file).unlink(missing_ok=True)
                    print(f"~> Failed to save image for {filename}: {e}. Skipping...")

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
        return Image.open(f"{_PRINTER_IMAGE_DIR_FULL}/{img_name}{IMAGE_EXTENSION}")
    elif mode == "art":
        return Image.open(f"{_PRINTER_IMAGE_DIR_ART}/{img_name}{IMAGE_EXTENSION}")
    else:
        raise ValueError("Invalid mode. Must be 'full' or 'art'.")
