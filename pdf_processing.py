
import io
from pdf2image import convert_from_bytes
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_pdf_to_images(file_bytes):
    """Converts a PDF file into a list of image URLs, one for each page."""
    logging.info("Starting PDF to image conversion.")
    try:
        output_folder = 'imgs'
        # Ensure the output directory exists
        os.makedirs(output_folder, exist_ok=True)

        # Clean up old images in the directory before processing new ones
        for f in os.listdir(output_folder):
            os.remove(os.path.join(output_folder, f))

        images = convert_from_bytes(file_bytes, dpi=300)

        image_urls = []
        for i, image in enumerate(images):
            filename = f"page_{i + 1}.png"
            filepath = os.path.join(output_folder, filename)
            image.save(filepath, "PNG")

            # The URL path the browser will use
            url_path = f"/{output_folder}/{filename}"
            image_urls.append(url_path)

            logging.info(f"Successfully converted and saved page {i + 1} to {filepath}.")

        return {"image_urls": image_urls}

    except Exception as e:
        logging.error("An unexpected error occurred during PDF to image conversion: %s", e, exc_info=True)
        return {"error": "Failed to convert PDF to images."}
