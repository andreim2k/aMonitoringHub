# Gemini to Perplexity API Migration Summary

## Date: 2025-09-30

## Changes Made

### 1. Configuration Update (`backend/config.json`)
- **Removed**: Gemini API configuration
- **Added**: Perplexity API configuration with:
  - API Key: `pplx-YOUR_API_KEY_HERE`
  - Model: `sonar-vision`
  - Custom Prompt: "Pay attention and look very carefully: extract me the number ONLY from the image! number is made from 4 digits! If you are not sure which is the last digit, just return exactly this text: 'Failed to read index!', else return only the number without any comment!"

### 2. Backend Code Update (`backend/app.py`)
- **Replaced**: Google Generative AI integration with Perplexity API
- **Updated**: `/webcam/ocr` route to use Perplexity's Chat Completions API
- **Implemented**: 
  - Proper error handling for Perplexity API calls
  - Image encoding as base64 data URL
  - Custom prompt from configuration
  - Response parsing with number extraction
  - Failure detection based on prompt response

### 3. Dependencies Update (`backend/requirements.txt`)
- **Removed**: `google-generativeai>=0.8.5`
- **Kept**: `requests>=2.32.0` (already present, now used for Perplexity API)
- **Kept**: `Pillow>=11.3.0` (for future image processing if needed)

## API Integration Details

### Perplexity API Endpoint
```
POST https://api.perplexity.ai/chat/completions
```

### Request Format
```json
{
  "model": "sonar-vision",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "<custom_prompt>"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,<base64_image>"
          }
        }
      ]
    }
  ]
}
```

### Response Handling
- Extracts text from `choices[0].message.content`
- Checks for failure message: "Failed to read index!"
- Extracts numeric values using regex
- Returns the longest numeric sequence found

## Testing Recommendations
1. Verify the Perplexity API endpoint is accessible
2. Test with sample electricity meter images
3. Validate the 4-digit number extraction
4. Confirm error handling for unclear images
5. Check API rate limits and response times

## Next Steps
If you need to test the new integration, you can:
1. Restart the backend service
2. Make a POST request to `/webcam/ocr`
3. Monitor the response for "Perplexity AI" engine confirmation
