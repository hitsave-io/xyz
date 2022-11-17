# Deploy Record

This is a detailed log of the steps I took to set up the production
HitSave deployment.

### 1. Created `CodeDeployPolicy` policy

This policy can be attached to roles and users. It provides access to
CodeDeploy resources and allows the holder to use the CodeDeploy API.

### 2. Instance role

In IAM, created `hitsave_production_server_role`. This is an instance
profile, which means you attach it to EC2 instances and they assume this
'role', which gives them the permissions policies associated with the
role.

Added the permissions policy `CodeDeployPolicy` to the role. I believe
that without this policy, the EC2 instance would not be able to accept
deployments from CodeDeploy.

### 3. Provisioned EC2 instance for running HitSave

Instance ID: i-0d4a81a7e7a62d18a
Instance type: t2.small

This EC2 instance will be used for running the docker containers for the
entire HitSave application.

Assigned the instance role `hitsave_production_server_role` from the
previous page.

Assigned a key pair which allows my PC to SSH into the instance.

Allocated two EBS volumes.

1. Standard filesystem volume for the instance
   - 8GB
   - /dev/xvda
   - Delete on termination: yes
2. Additional storage volume for Postgres data
   - 30GB
   - /dev/sdb
   - Delete on termination: no

# 4. Create filesystem for Postgres volume and mount it

SSH into instance and run `sudo lsblk -f` to see volumes and their
filesystems:

```console
[ec2-user@ip-172-31-3-205 ~]$ sudo lsblk -f
NAME    FSTYPE LABEL UUID                                 MOUNTPOINT
xvda
└─xvda1 xfs    /     d8605abb-d6cd-4a46-a657-b6bd206da2ab /
xvdb
```

Create filesystem for the Postgres volume `xvdb` by running `sudo mkfs -t xfs /dev/xvdb`.

```console
[ec2-user@ip-172-31-3-205 ~]$ sudo mkfs -t xfs /dev/xvdb
meta-data=/dev/xvdb              isize=512    agcount=4, agsize=1966080 blks
         =                       sectsz=512   attr=2, projid32bit=1
         =                       crc=1        finobt=1, sparse=0
data     =                       bsize=4096   blocks=7864320, imaxpct=25
         =                       sunit=0      swidth=0 blks
naming   =version 2              bsize=4096   ascii-ci=0 ftype=1
log      =internal log           bsize=4096   blocks=3840, version=2
         =                       sectsz=512   sunit=0 blks, lazy-count=1
realtime =none                   extsz=4096   blocks=0, rtextents=0
```

Now, the filesystem is ready:

```console
[ec2-user@ip-172-31-3-205 ~]$ sudo lsblk -f
NAME    FSTYPE LABEL UUID                                 MOUNTPOINT
xvda
└─xvda1 xfs    /     d8605abb-d6cd-4a46-a657-b6bd206da2ab /
xvdb    xfs          b62757bc-b143-414d-a8a3-c4d3cfc9f8ec
```

Create the Postgres data directory.

```console
sudo mkdir -p /var/pgdata
```

We don't need to mount this device to the filesystem, because Docker can
mount the device directly later.

### 5. Set up Docker on the instance

The steps are:

```bash
sudo yum update -y
sudo yum install docker -y

# Add the ec2-user to the docker group
sudo usermod -aG docker ec2-user
# To avoid having to log out and in again:
newgrp docker

# Create the directory for docker plugins
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins

# The latest `docker compose` can be found at the Releases page: https://github.com/docker/compose/releases
curl -SL https://github.com/docker/compose/releases/download/v2.12.2/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose

# Start docker
sudo systemctl start docker

# It should now be possible to run both `docker` and `docker compose`
docker version
docker compose version
```

### 6. Create a Docker volume using the EBS volume from step 4

Initially there are no volumes: `docker volume ls` returns nothing. To
set up the `pgdata` volume, run the following:

```bash
docker volume create --driver local \
--opt type=xfs \
--opt device=/dev/xvdb \
pgdata
```

We can now see the volume is known to docker:

```console
[ec2-user@ip-172-31-3-205 ~]$ docker volume ls
DRIVER    VOLUME NAME
local     pgdata
```

and we can inspect details about the volume:

```console
[ec2-user@ip-172-31-3-205 ~]$ docker volume inspect pgdata
[
    {
        "CreatedAt": "2022-11-16T14:29:21Z",
        "Driver": "local",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/volumes/pgdata/_data",
        "Name": "pgdata",
        "Options": {
            "device": "/dev/xvdb",
            "type": "xfs"
        },
        "Scope": "local"
    }
]
```

The device has been mounted at `/var/lib/docker/volumes/pgdata/_data`.

TODO: running `df` at this point doesn't show the xvdb drive. I think
that only when we run a `docker compose up` later and actually mount the
drive into the container will the device get mounted to the host system -
check if this prediction is true.

### 8. Set up S3 bucket for build artifacts

Set up a bucket where the GitHub workflow will upload build artifacts to
be retrieved by the CodeDeploy process on the application server.

- Bucket name: hitsave-prod-deploy-archive
- Region: eu-central-1
- Object ownership: ACLs disabled
- Block all public access
- Bucket versioning: enable
- Default encryption: disable

### 8. Set up CodeDeploy

#### a. Application

Create `hitsave-production` application in CodeDeploy console.

Create a Connection to GitHub, from the CodeDeploy console. This
involves logging in to the hitsave-io GitHub org to give CodeDeploy the
ability to download tarballs of our commits.

Next, you have to do something weird. The above step is not enough to
get CodeDeploy access to the GitHub repo for some reason. The weird
trick is to trigger a manual deploy for the deployment group, and
connect to GitHub in that process. Then it works.

#### b. Deployment group

Create `hitsave-production-codedeploy-service-role`, an IAM role which
includes just the AWS Managed `AWSCodeDeployRole` permissions policy.

Create `hitsave-prod-depgrp` deployment group for this application.

- Service role: `hitsave-production-codedeploy-service-role`
- Deployment type: in-place (we only have one instance in the group, so
  blue/green won't work yet; but I think blue/green is kind of emulated
  by `docker compose up`, which is nice.)
- Environment configuration: Amazon EC2 Instance
  - Tags (eventually, these tags can be used to differentiate between
    prod/staging environments, and application servers vs. cron workers
    etc.; but right now we only have this one server).
    - Name: hitsave_production_server_1
- Agent configuration (install CodeDeploy Agent): Now and schedule
  updates every 14 days
- Deployment settings: CodeDeployDefault.AllAtOnce (we only have one
  server, so this is fine).
- Load balancer: Disable load balancing (we need configure this when
  there is more than one server)
- Rollbacks: disabled for now
  - [See here](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployments-rollback-and-redeploy.html)
  - When a rollback happens, it actually just takes the last successful
    revision and redeploys it, which is not robust for us right now
    because that revision won't have access to the build archive in S3 (it
    may have been replaced by a build archive from the just-failed
    revision).
  - TODO: in the next step, we are going to set up the build archive
    bucket on S3 to be versioned. So it should be relatively easy to set
    up rollbacks which can access an earlier version of the build
    archive. What we can do is, in the final command of the
    ApplicationStart hook, we move the current `build.tar.gz` to
    `build.tar.gz-successful` or something, so when we rollback, we can
    grab the most recent successful version. This requires some careful
    bash scripting in the CodeDeploy hooks though, so not yet
    implemented.

#### c. IAM: policies and users

- Create a policy called `hitsave-production-gh-actions`
  with the correct permissions for writing to the S3 build archive bucket,
  and for triggering the creation of a new CodeDeploy deployment.
  Our GitHub workflow will authenticate as this user when it uploads the
  build archive to the bucket. We can give it very restricted permission -
  write-only to this specific bucket.
- Create a user `hitsave-production-gh-actions-codedeploy` for allowing
  GitHub actions workflow to programmatically access CodeDeploy and
  write to the S3 build archive bucket.
  - AWS credential type: Access key - Programmatic access
  - Policies: attach `hitsave-production-gh-actions` policy from
    previous step
  - This creates a new set of credentials for the user. Provide these to
    GitHub:
    - Go to `hitsave-io/xyz` and navigate to Settings > Environments
    - Create a new `production` environment
    - Add secrets: AWS_DEPLOY_ACCESS_KEY_I, AWS_DEPLOY_ACCESS_KEY_ID
- Create a policy called `hitsave-production-code-deploy`. This has
  quite broad permissions (TODO: probably much too broad) which allow
  the EC2 instance to work with the CodeDeploy at deployment time, as
  well as accessing S3 to get the build archive.
- Attach the `hitsave-production-code-deploy` policy to the
  `hitsave-production-server-role` role.

### 9. Set up S3 bucket for production BLOBs

Set up a bucket where BLOBs will be stored by the HitSave application.

- Bucket name: hitsave-prod-blobs
- Region: eu-central-1
- Object ownership: ACLs disabled
- Block all public access
- Bucket versioning: disable
- Default encryption: disable

Set up a policy for reading and writing to the this bucket called
`hitsave-production-blob-reader-writer`. It only has PutObject and
GetObject permissions, specifically for the `hitsave-prod-blobs` bucket.

Create a `hitsave-production-blob-reader-writer` user, with the
`hitsave-production-blob-reader-writer` policy attached, and with
programmatic access.

### 10. Organise xyz monorepo deploy directory

Organise this documentation under the /doc directory in the `xyz` monorepo.

#### Docker

Create a top-level `deploy` directory. In here, we store everything that
pertains to deployment of the application, which is mostly docker
related. The files are:

- `docker-compose.yml` - The base docker compose file. This has the
  config which is shared across all environments.
- `docker-compose.production.yml` - The production override. This has
  a couple of different environment variables and loads in the production
  Postgres volume.
- `api.Dockerfile` - Dockerfile for the Rust API
- `migrate.Dockerfile` - Dockerfile defining the image for a short-lived
  DB migration process. We may not need this soon, because I've set it
  up to use a compiled binary and the execution image is the same as
  that for the API. So we can probably just launch the API image with a
  `./deploy.sh` script which first runs migrations, then launches `hitsave`.
- `web.Dockerfile` - Dockerfile defining the image for the web server.
  This includes NodeJS and the build directories. Unfortunately, because
  of a current limitation of Remix, we are having to include the
  entirety of `node_modules` [see here](https://remix.run/docs/en/v1/pages/gotchas#importing-esm-packages)
- `nginx.Dockerfile` - Dockerfile defining the image for nginx. Docker
  compose launches a network among the services, so we can use nginx to
  handle traffic to port 80 (and eventually 443), forwarding the traffic
  to the relevant services.
- `nginx.conf` - Configuration to make the above work.

#### Secrets

In the deploy directory, we add a `.secrets` directory locally. Add the
secrets directory to `.gitignore`.

In general, our strategy for secrets management works like this:

- Never load secrets into environment variables. [This is bad practice.](https://www.trendmicro.com/en_us/research/22/h/analyzing-hidden-danger-of-environment-variables-for-keeping-secrets.html#:~:text=However%2C%20from%20a%20cloud%20security,than%20one%20instance%20of%20compromise.)
- Store secrets in files with restricted permissions.
- Maintain the secrets under the `deploy` directory in `deploy/.secrets`,
  since they need to be accessible to the docker compose context.
- Load the secrets via the `secrets` key in the docker-compose file.
- Pass secrets to applications by setting environment variables for
  their containers to the file names where the secrets are located (which
  will always be of the form `/run/secrets/{secret_file_name}` inside the
  container).
- From within the application, load the secret from the file specified
  in the environment variable.

Include secrets for:

- postgres password
  - note: we now build up the connection url from a few individual
    parameters, since the env var for the password is actually just the
    file where the secret password is stored; the application code
    builds the connection string by reading this secret file and
    composing the parts
- jwt private key
  - this just needs to be randomly generated with `openssl rand -base64 20`
- aws_s3_creds
  - this is for the application to read/write blobs in the S3 bucket created
    at step 9
  - we store a credentials file, of the form which is usually saved at
    `~/.aws/credentials`
- gh_client_secret
  - this is the secret key associated with the GitHub OAuth app we are
    using to register users

#### Nginx

Nginx doesn't, by default, allow you to use environment variables, but
the nginx docker image we're using does have a function which runs
before the main nginx process commences. This function looks at a
templates directory and outputs conf files to `/etc/nginx/conf.d/`,
loading environment variables in placeholders. These templates can include
environment variables with the syntax `${ENV_VAR}`. Using this
functionality, we can have different nginx configs for our different
environments, just by changing the environment variables.

This has all been reflected in the `deploy` directory.

[See here for more details.](https://hub.docker.com/_/nginx#:~:text=Using%20environment%20variables%20in%20nginx%20configuration%20(new%20in%201.19)

#### GitHub workflows

Added the GitHub workflow at `.github/workflows/release.yml`. This is a
single workflow to build the API and website, archive the build
artifacts to S3 and trigger a CodeDeploy deployment.

#### appspec.yml and hook scripts

CodeDeploy looks for a file called `appspec.yml` in the root of the
repository (so unfortunately we can't put this in `/deploy` with
everything else).

The final part of our GitHub workflow `deploy` is to trigger a
CodeDeploy deployment using the command `aws deploy create-deployment`.
The runner is able to do this, because it loaded permissions earlier in the
job, and we provided a key pair earlier which has CodeDeploy
permissions.

Our `appspec.yml` is currently quite basic. It provides scripts for two
deployment hooks, `BeforeInstall` and `AfterInstall`.

BeforeInstall simply removes the old `xyz` repo from the EC2 machine.

AfterInstall is more involved; it runs after the CodeDeploy agent has
pulled the GitHub repo for `xyz`. The `./after-install.sh` script
downloads the build archives from S3 (which were placed there by the
GitHub action). It then moves these build artifacts into their correct
locations in the `xyz` directory tree using `rsync`.

Finally, it starts the application by running `docker compose build` and
then `docker compose up -d`.

TODO: this last part should really happen in the ApplicationStart hook.

If all this goes according to plan, then the newly pushed commit is live
on the internet.

### 11. Create a GitHub OAuth app for HitSave

From the GitHub website, in Developer Settings > OAuth Apps, create a
new OAuth app called `HitSave` (this is the name that is visible to end
users, so shouldn't have a reference to 'production' in it! We will
eventually have a version called `HitSave-dev` or something, so that
the environments are kept separate.) Set the callback URL to
`https://hitsave.io/login`. Generate a client secret for this app.

### 12. Manually place secrets in restricted files on EC2 instance

Create a `~/.secrets` directory, owned by ec2-user. Add the following
secrets to the directory, each as a file:

- aws_s3_creds: a cred file for the user created at the end of step 9.
  This gives the API binary the ability to read and write to the blobs
  bucket.
- gh_client_secret: the secret generated in the GitHub UI at step 11.
  This gives the API the ability to authenticate end-users by allowing
  them to sign in with their GitHub account.
- jwt_priv: generate random private key with `openssl rand -base64 20`.
  If this changes, then all JWTs issued with the old signing key become
  invalid, effectively logging everyone out of HitSave.
- postgres_password: generate random private key again, with `openssl rand -base64 20`. The first time the Docker container runs the
  postgres image, postgres will create the HitSave DB with this
  password, and it will required thereafter. If we ever lose the
  password, then I think it becomes very hard to get back into the DB (maybe
  impossible? I actually don't know..). On the basis that this is a very
  important secret, I've saved it in my 1Password account, which I
  believe to be very secure.

### n. TLS Certificates

TODO
