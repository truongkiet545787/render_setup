FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (for building psycopg2 if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app
COPY . .

# Expose port
ENV PORT=8000
EXPOSE 8000

# Start FastAPI server
CMD ["python", "run.py"]
