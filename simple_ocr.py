@app.route("/ocr-simple")
def ocr_simple():
    """Simple OCR endpoint for testing"""
    try:
        import pytesseract
        from PIL import Image
        import re
        import io
        
        # Get cached image data
        image_data = get_cached_webcam_image()
        if not image_data:
            return jsonify({
                "success": False,
                "error": "Could not fetch webcam image",
                "index": "-----",
                "engine": "Simple Tesseract"
            }), 500
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        # Simple OCR without preprocessing
        raw_text = pytesseract.image_to_string(image).strip()
        
        # Also try with number-only config
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
        numbers_text = pytesseract.image_to_string(image, config=custom_config).strip()
        
        # Find all numbers
        numbers = re.findall(r'\d+', raw_text + ' ' + numbers_text)
        
        if numbers:
            # Join all numbers to form potential meter reading
            combined = ''.join(numbers)
            return jsonify({
                "success": True,
                "index": combined,
                "raw_text": raw_text,
                "numbers_text": numbers_text,
                "all_numbers": numbers,
                "engine": "Simple Tesseract"
            })
        else:
            return jsonify({
                "success": False,
                "index": "-----",
                "raw_text": raw_text,
                "numbers_text": numbers_text,
                "engine": "Simple Tesseract",
                "error": "No numeric patterns found"
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Simple OCR failed: {str(e)}",
            "index": "-----",
            "engine": "Simple Tesseract"
        }), 500

