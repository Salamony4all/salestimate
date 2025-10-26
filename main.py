
from flask import Flask, request, jsonify, render_template, send_from_directory
import logging
from logging.handlers import RotatingFileHandler
from pdf_processing import convert_pdf_to_images
from table_recognition import extract_table_from_image
import json
from dotenv import load_dotenv
import markdown
from bs4 import BeautifulSoup
import os

# Load environment variables from .env file
load_dotenv()

# --- Logging Configuration ---
logging.getLogger().handlers = []
file_handler = RotatingFileHandler('app.log', maxBytes=1024 * 1024, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
# ---

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/imgs/<path:filename>')
def serve_img(filename):
    return send_from_directory('imgs', filename)

@app.route('/process_pdf', methods=['POST'])
def process_pdf_route():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        try:
            file_bytes = file.read()
            #This function already returns a dict with the correct key
            image_urls = convert_pdf_to_images(file_bytes)
            return jsonify(image_urls)
        except Exception as e:
            logging.critical("Unhandled exception in /process_pdf: %s", e, exc_info=True)
            return jsonify({'error': 'An unexpected error occurred.'}), 500

def collate_tables(html_parts):
    """
    Cleans and collates multiple HTML tables into a single continuous HTML table.
    """
    final_header = None
    all_body_rows = []
    header_texts = []

    for html_part in html_parts:
        logging.info(f"Processing HTML part: {html_part}")
        if not html_part or not html_part.strip():
            continue

        soup = BeautifulSoup(html_part, 'html.parser')
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for i, row in enumerate(rows):
                is_header_or_separator = False
                cols = row.find_all(['th', 'td'])
                current_row_texts = [ele.text.strip().lower() for ele in cols]
                
                if current_row_texts in header_texts and len(header_texts) > 0:
                    is_header_or_separator = True
                
                if final_header is None and i == 0:
                    final_header = row
                    header_texts.append([ele.text.strip().lower() for ele in final_header.find_all(['th', 'td'])])
                    is_header_or_separator = True

                if not is_header_or_separator:
                    all_body_rows.append(row)
    
    if final_header is None:
        return ""

    new_table = BeautifulSoup('<table border="1"></table>', 'html.parser')
    new_table.table.append(final_header)
    for body_row in all_body_rows:
        new_table.table.append(body_row)

    return str(new_table)

@app.route('/collate_tables', methods=['POST'])
def collate_tables_route():
    data = request.get_json()
    if not data or 'markdown_parts' not in data:
        return jsonify({'error': 'Invalid request. Missing markdown_parts.'}), 400

    html_parts = data['markdown_parts']
    logging.info(f"Received {len(html_parts)} HTML parts for collation.")
    
    try:
        collated_html = collate_tables(html_parts)
        
        if not collated_html:
            logging.error("collate_tables returned an empty string. This can happen if no valid tables are found.")
            return jsonify({'error': 'Could not find any valid tables to collate in the selected pages.'}), 400

        return jsonify({'collated_html': collated_html})
    except Exception as e:
        logging.error(f"Error during table collation: {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred during table collation.'}), 500


@app.route('/extract_tables', methods=['POST'])
def extract_tables_route():
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400

    image = request.files['image']
    options_str = request.form.get('options', '{}')

    try:
        options = json.loads(options_str)
        image_bytes = image.read()
        
        api_result = extract_table_from_image(image_bytes, options)
        
        if api_result.get('error'):
            return jsonify({'error': api_result['error']}), 500

        if api_result.get('result', {}).get('layoutParsingResults'):
            first_result = api_result['result']['layoutParsingResults'][0]
            if 'markdown' in first_result and 'text' in first_result['markdown']:
                markdown_text = first_result['markdown']['text']
                return jsonify({'markdown_text': markdown_text}) 
            else:
                return jsonify({'markdown_text': ''})
        else:
            return jsonify({'markdown_text': ''})

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in options'}), 400
    except Exception as e:
        logging.critical("Unhandled exception in /extract_tables: %s", e, exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
