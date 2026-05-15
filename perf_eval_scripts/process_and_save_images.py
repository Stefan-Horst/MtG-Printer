from io import BytesIO
from pathlib import Path
from contextlib import nullcontext
from PIL import Image, ImageOps
import asyncio
import timeit
import aiofile
from card_handling.process_image import BLACK_WHITE_THRESHOLD, DEVICE_WIDTH, PRINTER_IMAGE_DIR, IMAGE_DIR

IMAGE_EXTENSION = ".png"
MAX_CONCURRENT_TASKS = 100

progress = 0

async def process_all_images(image_dir: str = IMAGE_DIR, 
                             output_dir: str = PRINTER_IMAGE_DIR, 
                             skip_existing: bool = True):
    input_path = Path(image_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    tasks = [process_image(image_file.name, image_dir, output_dir, skip_existing, sem) 
             for image_file in input_path.iterdir()
             if image_file.is_file() and image_file.suffix.lower() in [".jpg", ".jpeg", ".png"]]
    await asyncio.gather(*tasks)

async def process_image(file: str, 
                        image_dir: str = IMAGE_DIR, 
                        output_dir: str = PRINTER_IMAGE_DIR, 
                        skip_existing: bool = True, 
                        sem: asyncio.Semaphore = None) -> None:
    sem = sem or nullcontext() # without sempahore use placeholder context manager that does nothing
    async with sem:
        input_file = Path(image_dir) / file
        filename = input_file.stem
        try:
            img = Image.open(input_file)
            # resize to fit the printer
            ratio = img.size[0] / img.size[1]
            new_height = int(DEVICE_WIDTH / ratio)
            img = img.resize((DEVICE_WIDTH, new_height))
            # convert to grayscale
            gray = img.convert("L")
            # increase contrast
            gray = ImageOps.autocontrast(gray)
            # threshold to pure black/white
            bw = gray.point(lambda x: 0 if x < BLACK_WHITE_THRESHOLD else 255, "1")
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
    
    global progress
    progress += 1
    print("\b" * len(str(progress)), end="")
    print(str(progress), end="", flush=True)


print("0", end="", flush=True)
start_time = timeit.default_timer()
asyncio.run(process_all_images())
end_time = timeit.default_timer()
print(f"\nProcessed images in {end_time - start_time:.4f} seconds")
