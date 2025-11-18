# Use an official Python base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /code

# Copy the requirements file and install dependencies
# This step is cached to speed up future builds
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Command to run the app. Cloud Run provides the $PORT variable.
# We use 8080 as a default.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]