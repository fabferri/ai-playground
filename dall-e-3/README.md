# DALL-E Image Generation

This project demonstrates image generation using Azure OpenAI's DALL-E models.

## Files

- **aoai-app.py** - Generates images from text prompts using DALL-E 3. 
- **aoai-solution.py** - Demonstrates advanced DALL-E 3 usage with metaprompts for content safety.

## Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file with:
```
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=your-endpoint
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

## Important Notes

- **DALL-E 3**: Supports text-to-image generation only (PNG output)
- **DALL-E 2**: Supports generation, variations, and editing (PNG input/output required). Image variations require a DALL-E 2 deployment

`Tags: Azure OpenAI, dall-e 3` <br>
`date: 19-12-2025` <br>
