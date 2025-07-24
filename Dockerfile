# Use Playwright's official Docker image for Python
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy your requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set the entrypoint for your cron job.
CMD ["/bin/bash", "-c", "ls -la /app && /usr/bin/python3 /app/main.py 2>&1"]