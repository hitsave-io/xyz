FROM ubuntu:20.04

RUN apt-get -y upgrade \
  && apt-get -y update \
  && apt-get -y install libssl-dev

COPY /api/target/release/hitsave /usr/bin/hitsave

CMD ["hitsave", "-v"]