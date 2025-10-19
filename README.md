---
title: LLM Auto Deployer
emoji: 🤖
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# LLM Code Deployment Bot

This Space hosts the API endpoint for the LLM Code Deployment project. It uses Flask, Gemini, and PyGithub to automate the entire application build and deployment process.

## Overview

The LLM Code Deployment Bot is an automated system that receives deployment requests via API, uses Google's Gemini LLM to generate code, and deploys it to GitHub and Hugging Face Spaces.

## Features

- **API Endpoint**: RESTful API for receiving deployment requests
- **LLM Integration**: Uses Google Gemini to generate application code based on task descriptions
- **Automated GitHub Operations**: Creates repositories, commits code, and manages GitHub workflows
- **Hugging Face Deployment**: Automatically deploys applications to Hugging Face Spaces
- **Docker Support**: Containerized deployment for consistent environments

## Project Structure

- `app.py` - Flask application with API endpoint handler
- `handler.py` - Core logic for code generation, GitHub operations, and deployment
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration for deployment

## Usage

### API Endpoint

**URL**: `https://23f3004176-tds.hf.space/api-endpoint`

**Method**: `POST`

**Request Body** (JSON):
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-key",
  "task": "task-description",
  "round": "round-number",
  "nonce": "unique-nonce",
  "brief": "detailed-task-brief",
  "evaluation_url": "url-for-evaluation"
}
```

**Example using curl**:
```bash
curl -X POST https://23f3004176-tds.hf.space/api-endpoint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret-key",
    "task": "task-description",
    "round": "round-number",
    "nonce": "unique-nonce",
    "brief": "detailed-task-brief",
    "evaluation_url": "url-for-evaluation"
  }'
```

**Example using Python**:
```python
import requests

url = "https://23f3004176-tds.hf.space/api-endpoint"
data = {
    "email": "your-email@example.com",
    "secret": "your-secret-key",
    "task": "task-description",
    "round": "round-number",
    "nonce": "unique-nonce",
    "brief": "detailed-task-brief",
    "evaluation_url": "url-for-evaluation"
}

response = requests.post(url, json=data)
print(response.json())
```

## Dependencies

- Flask - Web framework
- google-generativeai - Gemini LLM integration
- PyGithub - GitHub API client
- requests - HTTP library

## Environment Variables

The following environment variables are required:
- `GITHUB_TOKEN` - GitHub personal access token
- `HF_TOKEN` - Hugging Face API token
- `GEMINI_API_KEY` - Google Gemini API key

## License

Apache License 2.0
