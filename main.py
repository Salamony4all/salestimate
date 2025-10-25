
from flask import Flask, request, jsonify, render_template
from pdf_processing import stitch_pdf_tables, crop_image_from_data
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_tables_route():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        try:
            file_bytes = file.read()
            # Correctly call the main processing function
            result = stitch_pdf_tables(file_bytes)
            if not result or not result.get('image_data') or result['image_data'] == "data:image/png;base64,":
                return jsonify({'error': 'No tables could be extracted from the PDF.'}), 400
            # Return the stitched image directly
            return jsonify({'stitched_image': result['image_data']})
        except Exception as e:
            logging.error(f"An error occurred during table extraction: {e}")
            return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/stitch', methods=['POST'])
def stitch_tables_route():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        try:
            file_bytes = file.read()
            result = stitch_pdf_tables(file_bytes)
            if not result or not result.get('image_data') or result['image_data'] == "data:image/png;base64,":
                return jsonify({'error': 'No tables could be extracted from the PDF.'}), 400
            return jsonify(result)
        except Exception as e:
            logging.error(f"An error occurred during table stitching: {e}")
            return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/crop', methods=['POST'])
def crop_route():
    data = request.json
    image_data = data.get('imageData')
    table_coordinates = data.get('tableCoordinates')
    if not image_data or not table_coordinates:
        return jsonify({'error': 'Missing image data or coordinates'}), 400
    
    try:
        cropped_images = crop_image_from_data(image_data, table_coordinates)
        return jsonify({'cropped_images': cropped_images})
    except Exception as e:
        logging.error(f"An error occurred during image cropping: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
