FROM continuumio/miniconda3

WORKDIR /app

RUN apt-get update && apt-get install -y libgl1 xvfb

ENV PYTHONOCC_OFFSCREEN_RENDERER=1

COPY run.sh /app
COPY requirements.txt /app
COPY . /app/framework

RUN conda create -n myenv python=3.10 -y
SHELL ["conda", "run", "-n", "myenv", "/bin/bash", "-c"]

RUN conda install -c conda-forge pythonocc-core -y
RUN pip install -r requirements.txt

RUN echo '#!/bin/bash' > run.sh && \
    echo 'source activate myenv' >> run.sh && \
    echo 'python /app/framework/main.py "$@"' >> run.sh && \
    chmod +x run.sh

ENTRYPOINT ["./run.sh"]
