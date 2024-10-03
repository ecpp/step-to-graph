# Use an official Miniconda image as the base
FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app
COPY framework /app/framework

# Create a Conda environment with Python 3.10
RUN conda create -n myenv python=3.10 -y
SHELL ["conda", "run", "-n", "myenv", "/bin/bash", "-c"]

# Install PythonOCC and other dependencies
RUN conda install -c conda-forge pythonocc-core -y
RUN pip install -r requirements.txt

# Create the run.sh script
RUN echo '#!/bin/bash' > run.sh && \
    echo 'source activate myenv' >> run.sh && \
    echo 'python /app/framework/main.py "$@"' >> run.sh && \
    chmod +x run.sh

# Set the entrypoint to the run script
ENTRYPOINT ["./run.sh"]