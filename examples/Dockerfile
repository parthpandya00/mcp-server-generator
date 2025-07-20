# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/requirements.txt

# Install the dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the mock server application code
COPY mock_server.py /app/mock_server.py

# Make port 8001 available to the world outside this container
EXPOSE 8001

# Define the command to run the application
CMD ["uvicorn", "mock_server:app", "--host", "0.0.0.0", "--port", "8001"]
