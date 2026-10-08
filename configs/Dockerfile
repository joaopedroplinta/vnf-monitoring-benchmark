FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    bpfcc-tools \
    python3-bpfcc \
    libpython3.12-dev \
    iproute2 \
    net-tools \
    curl \
    kmod \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages psutil==7.2.2 prometheus_client==0.25.0 docker==7.2.0

WORKDIR /app

CMD ["/bin/bash"]