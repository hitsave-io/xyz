FROM ubuntu

RUN apt-get -y upgrade \
  && apt-get -y update \
  && apt-get -y install wget \
  && wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.16_amd64.deb \
  && dpkg -i libssl1.1_1.1.1f-1ubuntu2.16_amd64.deb

COPY /api/target/release/migrate /usr/bin/migrate

CMD ["migrate"]
