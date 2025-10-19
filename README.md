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
- `STUDENT_SECRET` - Student secret key
- `GEMINI_API_KEY` - Google Gemini API key

## License
MIT License
