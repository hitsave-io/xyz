#!/bin/bash
set -xe

# Delete the old directory as needed.
if [ -d /home/ec2-user/xyz ]; then
    rm -rf /home/ec2-user/xyz
fi

mkdir -vp /home/ec2-user/xyz
