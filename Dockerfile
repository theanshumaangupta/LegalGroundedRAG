# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Add a non-root user (Hugging Face Spaces strictly runs as UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set the working directory in the container
WORKDIR /code

# Copy the requirements file into the container
COPY --chown=user ./requirements.txt /code/requirements.txt

# Install any needed packages specified in requirements.txt
# We use --no-cache-dir to keep the image size small
RUN pip install --user --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of the application code into the container
COPY --chown=user . /code

# Hugging Face expects the application to run on port 7860
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
