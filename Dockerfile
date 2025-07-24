# Use a base image that has Python 3.10 and is based on Debian Bullseye
FROM python:3.10-slim-bullseye

# Install necessary Playwright system dependencies as root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgtk-4-0 \
        libgraphene-1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        libgstreamer-gl1.0-0 \
        libenchant-2-2 \
        libsecret-1-0 \
        libmanette-0.2-0 \
        libgles2-mesa \
        # Additional Playwright dependencies often needed for Chromium:
        libnss3 \
        libxss1 \
        libasound2 \
        libgbm-dev \
        libnspr4 \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy your requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium for your script)
RUN playwright install chromium

# Copy the rest of your application code
COPY . .

# Set the entrypoint for your cron job.
CMD ["python", "main.py"]