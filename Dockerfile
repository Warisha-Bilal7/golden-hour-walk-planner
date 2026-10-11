FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /app

# Install system dependencies needed for geospatial and plotting packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and project definitions
COPY pyproject.toml README.md ./

# Copy source code
COPY src/ src/

# Install the Python package and its dependencies
RUN pip install --no-cache-dir -e .

# Create persistent/working directories for cache and output
RUN mkdir -p output data/cache

# Expose Gradio port
EXPOSE 7860

# Run the Gradio web application
CMD ["python", "-m", "ghwalk.webapp"]
