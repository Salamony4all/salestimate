
import base64
import io
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import logging
import collections

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_table_header(image):
    """Finds the primary table header, returning its precise top and bottom coordinates."""
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception as e:
        logging.error(f"OCR error in find_table_header: {e}")
        return None

    header_keywords = {
        "sn", "sl", "sr", "no", "s.no", "sl.no", "sr.no", "#", "item",
        "qty", "quantity", "qyt",
        "image", "img", "img_ref", "img.ref",
        "description", "desc", "details", "particulars",
        "unit", "uom",
        "rate", "price", "unit_rate", "unit.rate", "unitprice",
        "total", "amount", "amt"
    }

    lines = collections.defaultdict(list)
    for i in range(len(data['text'])):
        if int(data['conf'][i]) > 30 and data['text'][i].strip():
            line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            lines[line_key].append({
                'text': data['text'][i].lower().strip(), 'top': data['top'][i],
                'left': data['left'][i], 'width': data['width'][i], 'height': data['height'][i]
            })

    best_line = {'score': 0, 'bounds': None}
    img_width, _ = image.size
    for line_key, words in lines.items():
        found_keywords = [w for w in words if w['text'] in header_keywords]
        if len(found_keywords) >= 2:
            keyword_positions = [w['left'] for w in found_keywords]
            spread = (max(keyword_positions) - min(keyword_positions)) / img_width if len(keyword_positions) > 1 else 0
            score = len(found_keywords) + spread * 10
            if score > best_line['score']:
                y_min = min(w['top'] for w in words)
                y_max = max(w['top'] + w['height'] for w in words)
                best_line = {'score': score, 'bounds': (0, y_min, img_width, y_max)}

    if not best_line['bounds']:
        return None
    return best_line['bounds']

def _find_table_end_y(image, start_y):
    """Finds the y-coordinate for the end of a table based on vertical text gaps."""
    try:
        crop_area = (0, start_y, image.width, image.height)
        data = pytesseract.image_to_data(image.crop(crop_area), output_type=pytesseract.Output.DICT)
    except Exception as e:
        logging.error(f"OCR error in _find_table_end_y: {e}")
        return image.height

    lines = collections.defaultdict(list)
    for i in range(len(data['text'])):
        if int(data['conf'][i]) > 30 and data['text'][i].strip():
            line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            lines[line_key].append({'top': data['top'][i], 'height': data['height'][i]})

    if len(lines) < 2:
        return image.height

    sorted_keys = sorted(lines.keys(), key=lambda k: lines[k][0]['top'])
    last_line_bottom = max(w['top'] + w['height'] for w in lines[sorted_keys[0]])
    for i in range(len(sorted_keys) - 1):
        current_words, next_words = lines[sorted_keys[i]], lines[sorted_keys[i+1]]
        avg_height = sum(w['height'] for w in current_words) / len(current_words)
        current_bottom = max(w['top'] + w['height'] for w in current_words)
        next_top = min(w['top'] for w in next_words)
        gap = next_top - current_bottom
        if gap > avg_height * 2.5:
            return start_y + current_bottom
        last_line_bottom = max(w['top'] + w['height'] for w in next_words)
    return start_y + last_line_bottom

def extract_and_stitch_tables(file_bytes):
    """Reliable, flexible, and precise table extraction with robust error handling."""
    logging.info("Starting robust table extraction process with master error handling.")
    try:
        images = convert_from_bytes(file_bytes)
        header_page_idx, header_bounds = -1, None
        for i, img in enumerate(images):
            search_area = img.crop((0, int(img.height * 0.05), img.width, int(img.height * 0.9)))
            h_bounds = find_table_header(search_area)
            if h_bounds:
                offset_y = int(img.height * 0.05)
                header_page_idx, header_bounds = i, (h_bounds[0], h_bounds[1] + offset_y, h_bounds[2], h_bounds[3] + offset_y)
                logging.info(f"Header found on page {i + 1}.")
                break

        if header_page_idx == -1:
            logging.warning("No table header found in document.")
            return {'image_data': "data:image/png;base64,", 'table_coordinates': []}

        table_parts = []
        for i in range(header_page_idx, len(images)):
            img = images[i]
            start_y = header_bounds[1] if i == header_page_idx else int(img.height * 0.05)
            end_y = _find_table_end_y(img, start_y)

            if start_y >= end_y:
                logging.warning(f"Invalid crop dimensions on page {i+1}: start_y={start_y}, end_y={end_y}. Stopping stitch.")
                break

            crop_box = (0, start_y, img.width, end_y)
            table_parts.append(img.crop(crop_box))
            logging.info(f"Cropped page {i + 1} with box {crop_box}.")

            if end_y < img.height * 0.85:
                logging.info(f"Table likely ended on page {i+1}. Stopping stitch.")
                break

        if not table_parts:
            logging.warning("Failed to extract any table parts after finding header.")
            return {'image_data': "data:image/png;base64,", 'table_coordinates': []}

        stitched_image = Image.new('RGB', (images[0].width, sum(p.height for p in table_parts)))
        current_y = 0
        for part in table_parts:
            stitched_image.paste(part, (0, current_y))
            current_y += part.height

        buffered = io.BytesIO()
        stitched_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("ascii")
        
        logging.info("Successfully stitched table from PDF.")
        return {"image_data": f"data:image/png;base64,{img_str}", "table_coordinates": []}

    except Exception as e:
        logging.error("An unexpected error occurred in table extraction pipeline: %s", e, exc_info=True)
        return {'image_data': "data:image/png;base64,", 'table_coordinates': []}


def stitch_pdf_tables(file_bytes):
    return extract_and_stitch_tables(file_bytes)

def crop_image_from_data(image_data, table_coordinates):
    return []
