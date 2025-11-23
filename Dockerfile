# Use Python 3.12 slim as base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy the rest of the application
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Create data.db if it doesn't exist (SQLite database)
RUN touch /app/data.db

# Expose port 9000 (as per server.py)
EXPOSE 9000

# Run the server using uv
CMD ["uv", "run", "main.py", "run"]

