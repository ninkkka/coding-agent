FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x coding_agent.py reviewer_agent.py

CMD ["python", "coding_agent.py"]
