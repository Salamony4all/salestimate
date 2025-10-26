
import io
import base64
from pdf2image import convert_from_bytes
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_pdf_to_images(file_bytes):
    """
    Converts a PDF file into a list of Base64 encoded image data URLs, one for each page.
    This method is designed for serverless environments where file I/O is restricted.
    """
    logging.info("Starting PDF to image conversion in-memory.")
    try:
        images = convert_from_bytes(file_bytes, dpi=300)
        image_urls = []

        for i, image in enumerate(images):
            # Save image to an in-memory buffer
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            
            # Encode the image to Base64 and create a data URL
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            data_url = f"data:image/png;base64,{img_str}"
            image_urls.append(data_url)

            logging.info(f"Successfully converted page {i + 1} to a Base64 data URL.")

        return {"image_urls": image_urls}

    except Exception as e:
        # It's crucial to log the specific poppler error if it occurs
        if "Poppler" in str(e):
            logging.error("Poppler not found or configured correctly. Ensure it's installed on the system. Error: %s", e, exc_info=True)
            return {"error": "Server configuration error: Poppler dependency is missing."}
        
        logging.error("An unexpected error occurred during PDF to image conversion: %s", e, exc_info=True)
        return {"error": "Failed to convert PDF to images."}
