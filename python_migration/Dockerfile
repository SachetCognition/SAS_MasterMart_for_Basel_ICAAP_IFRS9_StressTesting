FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Oracle client
RUN apt-get update && apt-get install -y --no-install-recommends \
    libaio1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY config/ config/
COPY lib/ lib/
COPY extract/ extract/
COPY modules/ modules/
COPY dags/ dags/
COPY __init__.py .

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Default command
CMD ["python", "-m", "pytest", "tests/", "-v"]
