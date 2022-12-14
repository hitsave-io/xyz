#!/bin/bash

# Log the outputs of this script to stop-server.log
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>stop-server.log 2>&1

# Everything from here will be logged.
set -e

cd /home/ec2-user/xyz/deploy

# This should prevent the machine getting full of old docker garbage. Without
# this, we get docker crashing every nth deploy.
docker system prune

docker compose -p xyz-prod down
