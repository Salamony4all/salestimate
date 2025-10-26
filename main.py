
from flask import Flask, request, jsonify, render_template
import logging
from pdf_processing import convert_pdf_to_images
from table_recognition import extract_table_from_image
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

# --- Vercel Compatible Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
# ---

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

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
            # This function is now updated to return base64 data URLs
            image_urls = convert_pdf_to_images(file_bytes)
            return jsonify(image_urls)
        except Exception as e:
            logging.critical("Unhandled exception in /process_pdf: %s", e, exc_info=True)
            return jsonify({'error': 'An unexpected error occurred during PDF processing.'}), 500

def collate_html_tables_to_json(html_parts, image_maps):
    full_image_map = {k: v for d in image_maps for k, v in d.items()}
    master_table = []
    final_header_texts = []
    processed_header_signatures = set()

    for html_part in html_parts:
        if not html_part or not html_part.strip():
            continue
        soup = BeautifulSoup(html_part, 'html.parser')
        for img in soup.find_all('img'):
            if img.has_attr('src') and img['src'] in full_image_map:
                img['src'] = full_image_map[img['src']]
                img['style'] = 'max-width: 150px; height: auto;'
        table = soup.find('table')
        if not table:
            continue
        rows = table.find_all('tr')
        if not rows:
            continue

        header_row = rows[0]
        current_header_texts = [ele.text.strip() for ele in header_row.find_all(['th', 'td'])]
        header_signature = tuple(h.lower() for h in current_header_texts)
        if not final_header_texts:
            final_header_texts = current_header_texts
        processed_header_signatures.add(header_signature)

        for row in rows:
            row_texts_for_signature = [ele.text.strip().lower() for ele in row.find_all(['td', 'th'])]
            if tuple(row_texts_for_signature) in processed_header_signatures and tuple(row_texts_for_signature) != tuple(h.lower() for h in final_header_texts):
                continue
            if [ele.text.strip() for ele in row.find_all(['th', 'td'])] == final_header_texts:
                 continue

            cells = [cell.decode_contents() for cell in row.find_all(['td', 'th'])]
            if any(cells):
                master_table.append(cells)
    
    if not final_header_texts and master_table:
        final_header_texts = [f"Column {i+1}" for i in range(len(master_table[0]))]
    
    num_columns = len(final_header_texts)
    sanitized_rows = []
    if num_columns > 0:
        for row in master_table:
            sanitized_rows.append(row + [''] * (num_columns - len(row)))

    return {"headers": final_header_texts, "data": sanitized_rows}

@app.route('/collate_tables', methods=['POST'])
def collate_tables_route():
    data = request.get_json()
    if not data or 'html_parts' not in data or 'image_maps' not in data:
        return jsonify({'error': 'Invalid request. Missing html_parts or image_maps.'}), 400

    html_parts = data['html_parts']
    image_maps = data['image_maps']
    logging.info(f"Received {len(html_parts)} HTML parts and {len(image_maps)} image maps for collation.")
    
    try:
        table_json = collate_html_tables_to_json(html_parts, image_maps)
        if not table_json.get("headers") or not table_json.get("data"):
            logging.warning("collate_tables_to_json returned empty or incomplete data.")
            return jsonify({'error': 'Could not find any valid tables to collate.'}), 400
        return jsonify(table_json)
    except Exception as e:
        logging.error(f"Error during HTML table collation: {e}", exc_info=True)
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

        layout_results = api_result.get('result', {}).get('layoutParsingResults', [])
        if layout_results:
            first_result = layout_results[0]
            html_content = first_result.get('html', '')
            images = first_result.get('images', {})
            return jsonify({'html': html_content, 'images': images})
        else:
            return jsonify({'html': '', 'images': {}})

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in options'}), 400
    except Exception as e:
        logging.critical("Unhandled exception in /extract_tables: %s", e, exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
