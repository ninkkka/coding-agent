# LLM Code Deployment Bot 🤖

Automate LLM-based web app creation, repository setup, and deployment using Gemini, Flask, and PyGithub.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Usage](#usage)
- [API Endpoint](#api-endpoint)
- [Dependencies](#dependencies)
- [Environment Variables](#environment-variables)
- [License](#license)

## 🚀 Overview
LLM Code Deployment Bot receives structured deployment requests, generates code via Gemini (Google LLM), and deploys to GitHub and GitHub Pages in a single workflow.

## ✨ Features
- End-to-end deployment via POST request
- Secure authentication using student secret
- Gemini LLM-powered auto code generation
- Automated GitHub repository & Pages deployment
- Multi-round task evaluation (supports improvements and updates)

## 🛠️ Usage
1. **Clone the Repository:**
   ```bash
   git clone https://github.com/23f3004176/LLM-Code-Deployment.git
   cd LLM-Code-Deployment
   ```
2. **Install Requirements:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the Server:**
   ```bash
   python app.py
   ```

## 🔗 API Endpoint

**POST** `https://23f3004176-tds.hf.space/api-endpoint`

Payload example:
```json
{
  "email": "your-email@example.com",
  "secret": "your-student-secret",
  "task": "your-task-name",
  "round": 1,
  "nonce": "unique-nonce",
  "brief": "Your task description goes here.",
  "evaluation_url": "your-evaluator-endpoint"
}
```

Example request (Python):
```python
import requests
url = "https://23f3004176-tds.hf.space/api-endpoint"
data = {
    "email": "...",
    "secret": "...",
    "task": "...",
    "round": 1,
    "nonce": "...",
    "brief": "...",
    "evaluation_url": "..."
}
response = requests.post(url, json=data)
print(response.json())
```

## 📚 Dependencies
- Flask
- google-generativeai
- PyGithub
- requests

## ⚙️ Environment Variables
- `GITHUB_TOKEN` — GitHub personal access token
- `GEMINI_API_KEY` — Gemini API key
- `STUDENT_SECRET` — Your assigned secret key

## 📝 License
MIT License
