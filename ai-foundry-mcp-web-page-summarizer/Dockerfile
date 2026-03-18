FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements and install as root, then change ownership
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./

# Change ownership of the app directory to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# FastMCP runs on port 8000 (see server.py)
EXPOSE 8000

# Configure Python environment
ENV PYTHONUNBUFFERED=1

# The server loads from .env or expects these environment variables:
# - PROJECT_ENDPOINT (required)
# - MODEL_DEPLOYMENT_NAME (required)

CMD ["python", "server.py"]
