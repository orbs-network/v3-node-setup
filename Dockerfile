# This creates a temp image simulating an Ubuntu EC2 to test the installer script

FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ARG UBUNTU_VERSION=22.04

# Add sudo to make more like EC2 instance
RUN apt-get update && apt-get install -y fzf software-properties-common python3 python3-pip sudo locales vim curl

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

# Prepare to install podman 4.6.2
RUN key_url="https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/unstable/xUbuntu_${UBUNTU_VERSION}/Release.key" && \
sources_url="https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/unstable/xUbuntu_${UBUNTU_VERSION}" && \
echo "deb $sources_url/ /" | tee /etc/apt/sources.list.d/devel:kubic:libcontainers:unstable.list && \
curl -fsSL $key_url | gpg --dearmor | tee /etc/apt/trusted.gpg.d/devel_kubic_libcontainers_unstable.gpg && \
apt-get update

ARG INSTALL_PACKAGES="podman fuse-overlayfs openssh-client ucpp"

# Update the package list and install required packages.
RUN apt-get install -y $INSTALL_PACKAGES && \
    ln -s /usr/bin/ucpp /usr/local/bin/cpp && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Prepare necessary stuff to let podman run as rootless.

RUN echo "ubuntu:1:999\nubuntu:1001:64535" > /etc/subuid && \
    echo "ubuntu:1:999\nubuntu:1001:64535" > /etc/subgid

ADD /containers.conf /etc/containers/containers.conf
ADD /podman-containers.conf /home/podman/.config/containers/containers.conf

RUN mkdir -p /home/ubuntu/.local/share/containers && \
    chown ubuntu:ubuntu -R /home/ubuntu && \
    chmod 644 /etc/containers/containers.conf

# Modify storage configuration for running with fuse-overlay storage inside the container
RUN sed -e 's|^#mount_program|mount_program|g' \
           -e '/additionalimage.*/a "/var/lib/shared",' \
           -e 's|^mountopt[[:space:]]*=.*$|mountopt = "nodev,fsync=0"|g' \
           /usr/share/containers/storage.conf \
           > /etc/containers/storage.conf

# Setup internal Podman to pass subscriptions down from host to internal container
RUN printf '/run/secrets/etc-pki-entitlement:/run/secrets/etc-pki-entitlement\n/run/secrets/rhsm:/run/secrets/rhsm\n' > /etc/containers/mounts.conf

# Define volumes for container storage
VOLUME /var/lib/containers
VOLUME /home/ubuntu/.local/share/containers

# Create shared directories and locks
RUN mkdir -p /var/lib/shared/overlay-images \
             /var/lib/shared/overlay-layers \
             /var/lib/shared/vfs-images \
             /var/lib/shared/vfs-layers && \
    touch /var/lib/shared/overlay-images/images.lock && \
    touch /var/lib/shared/overlay-layers/layers.lock && \
    touch /var/lib/shared/vfs-images/images.lock && \
    touch /var/lib/shared/vfs-layers/layers.lock

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY .bashrc /home/ubuntu/.bashrc
RUN chown ubuntu:ubuntu /home/ubuntu/.bashrc

USER ubuntu

WORKDIR /home/ubuntu

## Shortcuts for docker-compose actions
#RUN echo 'alias dc="docker-compose"' >> ~/.bashrc
#RUN echo 'alias logs="docker-compose -f /home/ubuntu/deployment/docker-compose.yml logs"' >> ~/.bashrc
#RUN echo 'alias n-logs="docker-compose -f /home/ubuntu/deployment/docker-compose.yml logs nginx"' >> ~/.bashrc
#RUN echo 'alias ms-logs="docker-compose -f /home/ubuntu/deployment/docker-compose.yml logs ethereum-reader"' >> ~/.bashrc
#RUN echo 'alias ew-logs="docker-compose -f /home/ubuntu/deployment/docker-compose.yml logs ethereum-writer"' >> ~/.bashrc
#RUN echo 'alias s-logs="docker-compose -f /home/ubuntu/deployment/docker-compose.yml logs signer"' >> ~/.bashrc
#RUN echo 'alias ms-exec="docker-compose -f /home/ubuntu/deployment/docker-compose.yml exec ethereum-reader sh"' >> ~/.bashrc
#RUN echo 'alias ew-exec="docker-compose -f /home/ubuntu/deployment/docker-compose.yml exec ethereum-writer sh"' >> ~/.bashrc
#RUN echo 'alias s-exec="docker-compose -f /home/ubuntu/deployment/docker-compose.yml exec signer sh"' >> ~/.bashrc

COPY --chown=ubuntu:ubuntu setup setup
COPY --chown=ubuntu:ubuntu manager manager
COPY --chown=ubuntu:ubuntu deployment deployment
COPY --chown=ubuntu:ubuntu logging logging

ENTRYPOINT ["/entrypoint.sh"]
