#!/bin/bash
set -xe
cd /home/ec2-user

# Download the S3 build archive.
aws s3 cp s3://hitsave-prod-deploy-archive/build.tar.gz build.tar.gz

# Extract the build archive.
tar -xzf build.tar.gz
rm build.tar.gz

# Move the files to their correct locations. Since these directions may not be 
# empty, we use rsync.
rsync -a -v api/* xyz/api/
rsync -a -v web/* xyz/web/

# TODO - clean the base directory
rm -rf api
rm -rf web

# Move to repo directory
cd xyz/deploy

# Create symlinks to the secrets stored in ~/.secrets
ln -s ~/.secrets .secrets

# Build latest docker compose images
docker compose build

# Launch application containers, using production version of docker-compose.yml
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d

