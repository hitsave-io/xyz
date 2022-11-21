#!/bin/bash

# Log the outputs of this script to after-install.log
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>after-install.log 2>&1

# Everything from here will be logged.
set -xe
cd /home/ec2-user

# Download the S3 build archive.
aws s3 cp s3://hitsave-prod-deploy-archive/build.tar.gz build.tar.gz

# Extract the build archive.
tar -xzf build.tar.gz
rm build.tar.gz

# Move the files to their correct locations. Since these directories may not be 
# empty, we use rsync.
rsync -a -v api/* xyz/api/
rsync -a -v web/* xyz/web/
mv xyz/web/tailwind.css xyz/web/src/tailwind.css

# TODO - clean the base directory
rm -rf api
rm -rf web

# Move to repo directory
cd xyz/deploy

# Create symlinks to the secrets stored in ~/.secrets
ln -s ~/.secrets .secrets

# Build latest docker compose images
docker compose -p xyz-prod -f docker-compose.yml -f docker-compose.production.yml build

# Launch application containers, using production version of docker-compose.yml
docker compose -p xyz-prod -f docker-compose.yml -f docker-compose.production.yml up -d

