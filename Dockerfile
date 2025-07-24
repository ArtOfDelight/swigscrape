# Use Playwright's official Docker image for Python
# This image comes with Playwright's browser binaries and system dependencies pre-installed.
# It includes Python, Node.js, and browser binaries (Chromium, Firefox, WebKit).
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy your requirements.txt and install Python dependencies
# Playwright is already in the base image, so pip will just report "satisfied" for it.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set the entrypoint for your cron job.
CMD ["python", "main.py"]