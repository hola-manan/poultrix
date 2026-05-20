FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including GDAL
RUN apt-get update && apt-get install -y \
    gcc \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment — src/ layout means jeevn.* lives under /app/src
ENV PYTHONPATH=/app/src

# Expose API port
EXPOSE 8000

# Run API
CMD ["uvicorn", "jeevn.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
