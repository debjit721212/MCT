# Use official Python slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose FastAPI and Streamlit ports
EXPOSE 8088 8501

# Run both FastAPI and Streamlit with auto-reload
CMD ["sh", "-c", "\
  uvicorn api_server:app --host 0.0.0.0 --port 8088 --reload & \
  streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0"]
