FROM python:3.12-slim

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db ./db
COPY worker .

# Coolify scheduled task invokes: python main.py all
CMD ["python", "main.py", "all"]
