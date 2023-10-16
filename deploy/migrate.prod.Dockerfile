FROM ubuntu

RUN apt-get -y upgrade \
  && apt-get -y update \
  && apt-get -y install libssl1.1

COPY /api/target/release/migrate /usr/bin/migrate

CMD ["migrate"]
