FROM ubuntu

# Install package dependencies.
RUN apt-get -y update \
  && apt-get install -y \
  apt-utils \
  curl \
  libssl-dev \
  pkg-config \
  musl-tools \
  gcc \
  wget \
  && rm -rf /var/lib/apt/lists/*

# Install Rust.
RUN curl https://sh.rustup.rs -sSf > /tmp/rustup-init.sh \
    && chmod +x /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y \
    && rm -rf /tmp/rustup-init.sh
ENV PATH="$PATH:~/.cargo/bin"
RUN echo $PATH

# Update the local crate index
RUN ~/.cargo/bin/cargo search

# Install nightly rust.
RUN ~/.cargo/bin/rustup install nightly-2022-10-16

CMD ~/.cargo/bin/cargo run --release --bin=migrate -- -vv
