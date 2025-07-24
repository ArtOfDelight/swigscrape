# Use a base image that has Python 3.10 and is based on Debian Bullseye
FROM python:3.10-slim-bullseye

# Install necessary Playwright system dependencies as root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libwoff1 \
        libharfbuzz-icu0 \
        libgdk-pixbuf-2.0-0 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdrm-common \
        libepoxy0 \
        libfontconfig1 \
        libglib2.0-0 \
        libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        libjpeg-turbo8 \
        liblcms2-2 \
        libnss3 \
        libopenjp2-7 \
        libpng16-16 \
        libwebp6 \
        libwebpdemux2 \
        libwebpmux3 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        libxrender1 \
        libxshmfence6 \
        libxtst6 \
        xdg-utils \
        # These are specific to your previous errors and often needed for GTK/rendering:
        libgtk-3-0 \
        libgraphene-1.0-0 \
        libgles2 \
        libenchant-2-2 \
        libsecret-1-0 \
        libmanette-0.2-0 \
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