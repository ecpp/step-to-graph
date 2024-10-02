# Use an official Miniconda image as the base
FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Create a Conda environment with Python 3.10
RUN conda create -n myenv python=3.10 -y
SHELL ["conda", "run", "-n", "myenv", "/bin/bash", "-c"]

# Install PythonOCC and other dependencies
RUN conda install -c conda-forge pythonocc-core -y
RUN pip install -r requirements.txt

# Make the run script executable
RUN chmod +x run.sh

# Set the entrypoint to the run script
ENTRYPOINT ["./run.sh"]