# OpenRouter API Integration Guide

## Summary
Successfully migrated from Gemini API → Perplexity API → OpenRouter API for OCR functionality.

**Date**: 2025-09-30

## Why OpenRouter?
- ✅ **Unified API** for multiple AI models (GPT-4, Claude, Gemini, etc.)
- ✅ **Vision Support** for OCR and image analysis
- ✅ **Pay-as-you-go** pricing across different models
- ✅ **No vendor lock-in** - easy to switch models
- ✅ **Simple REST API** compatible with OpenAI format

## Configuration

### 1. Get Your OpenRouter API Key
1. Visit: https://openrouter.ai/
2. Sign up or log in
3. Go to "Keys" section
4. Create a new API key
5. Copy your key (starts with `sk-or-v1-...`)

### 2. Update Config File
Edit `/home/andrei/aMonitoringHub/backend/config.json`:

```json
{
  "ocr": {
    "engines": {
      "openrouter": {
        "api_key": "YOUR_ACTUAL_OPENROUTER_KEY_HERE",
        "model": "openai/gpt-4o"
      }
    }
  }
}
```

### 3. Available Vision Models
You can use any of these models in the config:

**Recommended (Best Quality):**
- `openai/gpt-4o` - GPT-4 Omni (best OCR, fast)
- `openai/gpt-4-vision-preview` - GPT-4 Vision
- `anthropic/claude-3-opus` - Claude 3 Opus (very good)

**Budget-Friendly:**
- `anthropic/claude-3-haiku` - Claude 3 Haiku (fast, cheaper)
- `google/gemini-pro-vision` - Gemini Pro Vision
- `openai/gpt-4o-mini` - GPT-4 Omni Mini (cheapest)

**Performance Options:**
- `anthropic/claude-3-sonnet` - Claude 3 Sonnet (balanced)

## Implementation Details

### API Endpoint
```
POST https://openrouter.ai/api/v1/chat/completions
```

### Request Format
```json
{
  "model": "openai/gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Your OCR prompt here..."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,<base64_encoded_image>"
          }
        }
      ]
    }
  ]
}
```

### Headers Required
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
HTTP-Referer: http://localhost:5000  (optional)
X-Title: aMonitoringHub OCR  (optional)
```

## Testing

### 1. Update API Key
```bash
nano /home/andrei/aMonitoringHub/backend/config.json
# Replace YOUR_OPENROUTER_API_KEY_HERE with your actual key
```

### 2. Restart App
```bash
bash /home/andrei/aMonitoringHub/scripts/app.sh restart
```

### 3. Test OCR Endpoint
```bash
curl -X POST http://192.168.50.2:5000/webcam/ocr
```

Expected response:
```json
{
  "success": true,
  "index": "1234",
  "engine": "OpenRouter (openai/gpt-4o)",
  "timestamp": "2025-09-30T16:30:00Z",
  "raw_ocr": "1234"
}
```

## Custom Prompt
The system uses your specific prompt:
> "Pay attention and look very carefully: extract me the number ONLY from the image! number is made from 4 digits! If you are not sure which is the last digit, just return exactly this text: 'Failed to read index!', else return only the number without any comment!"

## Cost Considerations

OpenRouter pricing (approximate):
- **GPT-4o**: ~$2.50 per 1M tokens (very cheap for images)
- **GPT-4o-mini**: ~$0.15 per 1M tokens (ultra cheap)
- **Claude 3 Haiku**: ~$0.25 per 1M tokens
- **Claude 3 Sonnet**: ~$3 per 1M tokens
- **Claude 3 Opus**: ~$15 per 1M tokens

For OCR of electricity meter images (small images, short responses):
- Estimated: **$0.001 - $0.01 per request**
- 1000 readings: **$1 - $10**

## Troubleshooting

### Error: "OpenRouter API key not configured"
→ Update config.json with your actual API key

### Error: 401 Unauthorized
→ Check your API key is valid and has credits

### Error: 400 Bad Request with model name
→ Check model name in config.json matches available models

### No response or timeout
→ Check internet connectivity and OpenRouter status

## Next Steps

1. **Get API Key**: Visit https://openrouter.ai/keys
2. **Update Config**: Edit `backend/config.json`
3. **Restart App**: Run `app.sh restart`
4. **Test**: Try the OCR endpoint

---

**Support**: https://openrouter.ai/docs
**Models List**: https://openrouter.ai/models
**Pricing**: https://openrouter.ai/docs/pricing
