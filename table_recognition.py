
import base64
import requests
import logging
import os

API_URL = os.environ.get("TABLE_API_URL")
TOKEN = os.environ.get("TABLE_API_TOKEN")

def extract_table_from_image(image_bytes, options):
    """Calls the Table Recognition API to extract tables from an image."""
    logging.info(f"Sending image to Table Recognition API with options: {options}")

    if not API_URL or not TOKEN:
        logging.error("API URL or token not configured. Please set TABLE_API_URL and TABLE_API_TOKEN in your .env file.")
        return {"error": "API credentials not configured."}

    try:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        headers = {
            "Authorization": f"token {TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "file": image_b64,
            "fileType": 1,  # 1 for image files
            **options
        }

        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            logging.info("Successfully received response from Table Recognition API.")
            return response.json()
        else:
            logging.error(f"API request failed with status code {response.status_code}: {response.text}")
            return {"error": f"API request failed: {response.status_code}"}

    except Exception as e:
        logging.critical("An unexpected error occurred while calling the Table Recognition API: %s", e, exc_info=True)
        return {"error": "An unexpected error occurred."}
