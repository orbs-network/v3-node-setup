# This creates a temp image to test the installer script

FROM ubuntu:22.10
ARG DEBIAN_FRONTEND=noninteractive

# Add sudo to make more like EC2 instance
RUN apt-get update && apt-get install -y software-properties-common python3 python3-pip sudo locales

# EC2 instances usually have locale settings
RUN locale-gen en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 \
  LANGUAGE=en_US:en \
  LC_ALL=en_US.UTF-8

# Needed to allow crons to run in the container
RUN echo "#!/bin/sh\nexit 0" > /usr/sbin/policy-rc.d

# Use non-root user (Docker by default uses root)
RUN useradd -ms /bin/bash ubuntu && \
  echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
  chmod 0440 /etc/sudoers.d/ubuntu
USER ubuntu

WORKDIR /home

COPY --chown=ubuntu:ubuntu setup setup
COPY --chown=ubuntu:ubuntu manager manager
COPY --chown=ubuntu:ubuntu deployment deployment

CMD ["/bin/bash"]
