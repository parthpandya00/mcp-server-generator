# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the application source code
COPY ./src /app/src

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the app. The Uvicorn server is a good choice for development.
# For production, you might want to use Gunicorn as a process manager.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
