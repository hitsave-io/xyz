#!/bin/bash

# Log the outputs of this script to after-install.log
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>before-install.log 2>&1

# Everything from here will be logged.
set -xe

# Delete the old directory as needed.
if [ -d /home/ec2-user/xyz ]; then
    rm -rf /home/ec2-user/xyz
fi

mkdir -vp /home/ec2-user/xyz
