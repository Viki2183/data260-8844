# Use Python because the application runs FastAPI and Uvicorn.
FROM python:3.12-slim

# Keep application files inside the container's /app directory.
WORKDIR /app

# Install the exact project dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application and frontend files.
COPY code/web_application ./web_application

# The container will expose FastAPI on port 80.
EXPOSE 80

# Start the FastAPI server when the container launches.
CMD ["uvicorn", "web_application.main:app", "--host", "0.0.0.0", "--port", "80"]