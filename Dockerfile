# Use a base image that already has some common Python and Node.js tools
FROM python:3.10-slim-buster

# Install necessary Playwright system dependencies as root
# These are the libraries that were listed as missing by Playwright
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
# Since system dependencies are installed, this should just download the browser binaries
RUN playwright install chromium

# Copy the rest of your application code
COPY . .

# Set the entrypoint for your cron job.
# This will be the command Render executes.
CMD ["python", "main.py"]