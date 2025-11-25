# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Make port 5002 available to the world outside this container
EXPOSE 5002

# Define environment variables (can be overridden at runtime)
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the command to start the Flask application
# We will have two processes: the Flask app and the RabbitMQ consumer.
# A better approach in production would be to use a process manager like supervisord,
# or run them in separate containers. For simplicity here, we'll start the web server.
# The consumer can be started manually or with another script.
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]

# To run the consumer, you could use a command like:
# CMD ["python", "-m", "app.consumer"]
