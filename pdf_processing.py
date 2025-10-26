
import base64
import io
from pdf2image import convert_from_bytes
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_pdf_to_images(file_bytes):
    """Converts a PDF file into a list of PNG images, one for each page."""
    logging.info("Starting PDF to image conversion.")
    try:
        # Convert PDF to a list of PIL images
        images = convert_from_bytes(file_bytes, dpi=300) # Use 300 DPI for high quality
        
        image_data_urls = []
        for i, image in enumerate(images):
            # Convert PIL image to PNG in memory
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            
            # Encode to Base64 and create data URL
            img_str = base64.b64encode(buffered.getvalue()).decode("ascii")
            data_url = f"data:image/png;base64,{img_str}"
            image_data_urls.append(data_url)
            
            logging.info(f"Successfully converted page {i + 1}.")

        return {"image_urls": image_data_urls}

    except Exception as e:
        logging.error("An unexpected error occurred during PDF to image conversion: %s", e, exc_info=True)
        return {"error": "Failed to convert PDF to images."}
