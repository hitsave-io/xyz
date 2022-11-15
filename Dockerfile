FROM ubuntu

RUN apt-get -y update \
  && apt-get -y install wget \
# RUN apt-get -y install openssl build-essential libssl-dev
  && wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.16_amd64.deb \
  && dpkg -i libssl1.1_1.1.1f-1ubuntu2.16_amd64.deb

COPY /api/target/release/hitsave /usr/bin/hitsave

CMD ["hitsave", "-v"]
