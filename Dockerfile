# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the local code to the container image
COPY . .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Specify the command to run on container start
CMD ["gunicorn", "--bind", ":8080", "main:app"]
