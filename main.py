
from flask import Flask, request, jsonify, render_template
import logging
from logging.handlers import RotatingFileHandler
from pdf_processing import convert_pdf_to_images
from table_recognition import extract_table_from_image
import json
from dotenv import load_dotenv
import markdown

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
            result = convert_pdf_to_images(file_bytes)
            return jsonify(result)
        except Exception as e:
            logging.critical("Unhandled exception in /process_pdf: %s", e, exc_info=True)
            return jsonify({'error': 'An unexpected error occurred.'}), 500

def collate_markdown_tables(markdown_parts):
    """
    Cleans and collates multiple markdown tables into a single continuous table.
    It removes non-table text and duplicate headers, preserving row order.
    """
    final_header = None
    final_separator = None
    final_body_rows = [] # Use a list to preserve order

    for md_part in markdown_parts:
        if not md_part or not md_part.strip():
            continue

        lines = [line.strip() for line in md_part.strip().split('\n')]
        
        # Find the table structure (header, separator, and body) in this part
        header_candidate = None
        separator_candidate_index = -1

        for i, line in enumerate(lines):
            is_separator = '|' in line and all(c in '|-: ' for c in line)
            if is_separator and i > 0 and '|' in lines[i-1]:
                # Found a potential table
                header_candidate = lines[i-1]
                separator_candidate_index = i
                
                # Use the first valid table's header and separator
                if final_header is None:
                    final_header = header_candidate
                    final_separator = lines[separator_candidate_index]

                # Process the body rows of THIS table
                for body_line in lines[separator_candidate_index + 1:]:
                    # A valid body row must contain '|'
                    if '|' not in body_line:
                        continue
                    
                    # It must not be another separator line
                    is_another_separator = all(c in '|-: ' for c in body_line)
                    if is_another_separator:
                        continue
                        
                    # It must not be a duplicate of the main header
                    # Compare content without whitespace and in lowercase
                    row_content = "".join(body_line.lower().split())
                    header_content = "".join(final_header.lower().split())
                    if row_content == header_content:
                        continue

                    # Add the row if it's not already in our final list
                    if body_line not in final_body_rows:
                        final_body_rows.append(body_line)
                
                # Since we found and processed the table in this part, we can stop searching this part
                break

    if final_header is None:
        return ""

    # Reconstruct the full, clean markdown table string
    return '\n'.join([final_header, final_separator] + final_body_rows)


@app.route('/collate_tables', methods=['POST'])
def collate_tables_route():
    data = request.get_json()
    if not data or 'markdown_parts' not in data:
        return jsonify({'error': 'Invalid request. Missing markdown_parts.'}), 400

    markdown_parts = data['markdown_parts']
    logging.info(f"Received {len(markdown_parts)} markdown parts for collation.")
    
    try:
        collated_md = collate_markdown_tables(markdown_parts)
        if not collated_md:
            logging.error("collate_markdown_tables returned an empty string. This can happen if no valid tables are found in the selected pages.")
            return jsonify({'error': 'Could not find any valid tables to collate in the selected pages.'}), 400

        collated_html = markdown.markdown(collated_md, extensions=['tables'])
        
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
                # This is a valid case if the page has no tables
                return jsonify({'markdown_text': ''})
        else:
            # Also a valid case for no tables
            return jsonify({'markdown_text': ''})

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in options'}), 400
    except Exception as e:
        logging.critical("Unhandled exception in /extract_tables: %s", e, exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
