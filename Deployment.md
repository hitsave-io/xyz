# HitSave Deployment

Because deployment is so bloody complicated, I've written down how
everything works here, so I don't have to try and keep this memorised
for the rest of my life.

## CodeDeploy

[CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/welcome.html)
is the AWS service for automating application deployments to AWS
infrastructure. It can be invoked from a GitHub action. The main
benefits are that we get to define different environments (production /
staging) and it will deploy to these, and it also handles zero-downtime
deploys for us (known as blue/green deploys).

Docs:

- [Components of CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/primary-components.html)

CodeDeploy is controlled by a `.appspec.yaml` file in the root of the
repository. This defines the deployment actions we want CodeDeploy to
execute.

Each EC2 instance running in production has a daemon called the
CodeDeploy agent running on it. I installed that manually on the instance
using [these steps](https://docs.aws.amazon.com/codedeploy/latest/userguide/codedeploy-agent-operations-install-linux.html).

To use CodeDeploy, we have defined a [Deployment Group](https://docs.aws.amazon.com/codedeploy/latest/userguide/primary-components.html#primary-components-deployment-group).
As part of configuring the Deployment Group, AWS Systems Manager will
automatically ensure that the AWS CodeDeploy agent is running on each
instance (so the manual steps above shouldn't ever be necessary). Note:
AWS Systems Manager is automatically installed on each EC2 instance when
you provision it.

We have a CodeDeploy user with credentials (ACCESS_KEY_ID and SECRET_KEY).
This user has a policy associated which allows access to CodeDeploy. We
give the ACCESS_KEY_ID and SECRET_KEY to GitHub secrets, which are
accessed from the `Deploy` workflow.

We're using [this GitHub Action](https://github.com/webfactory/create-aws-codedeploy-deployment)
to trigger CodeDeploy on pushes to main. See the `.github/workflows/deployment.yml`.
As per the README for the action, we have to include some additional config
in `.appspec.yml` to control the behaviour of the action. It's here that
we can define what happens to different branches. Subkeys of `branch_config`
are evaluated as regular expressions, and can be targeted at different
Deployment Groups. So we would have a deployment group for `production`
and another for `staging`, for example. And we could even have new groups
created for every pull request.

We need to access the build artifacts that get created in the various
GitHub actions. When we were using Render, we had a build script which
ran in both CI and on the production server at deploy time. It seems
wasteful to build the artifacts twice, so a better option is to take the
output from CI and put it in an S3 bucket to be accessed by CodeDeploy.

Notes:

- In order for the CodeDeploy agent to be able to download the repo, you
  need to give access to the CodeDeploy application in GitHub. Easiest
  way to do this is to go through the manual 'Create Deployment' steps
  in the AWS CodeDeploy console. Once done, all future deployments should
  work automatically.
- CodeDeploy offers a 'blue/green deployment' strategy, which implements
  the zero-downtime idea of provisioning new instances before taking
  down the old one, using a load balancer to transition traffic.
- The blue/green deployment type requires some further work to set up,
  so initially I'm using the 'in-place' deployment type, which briefly
  takes offline the instance while the CodeDeploy update occurs.

## GitHub Actions

- Our GitHub actions need to upload the build artifacts to S3, so we can
  retrieve them from the CodeDeploy side in AWS.

Notes:

- OIDC (OpenID Connect) - the point of this is to allow Github and AWS
  to communicate without storing long-lived access credentials in GitHub
  secrets. This is not implemented yet.
  - [Rationale](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
  - [Docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)

## Docker

We want to run all our apps in Docker containers. This includes the API
binary (called `hitsave`), the web app (which is a NodeJS server), and a
Postgres instance connected to EBS persistent storage.

The correct way to do this is with Docker Compose. It's bad practice to
put all the services in a single container - each service should have
its own container, and Docker Compose launches them all into a 'swarm'
which are networked together. You can also expose ports from each
container to the world outside the swarm.

Our swarm has to use a 'volume' for the persistent Postgres data. This
is easily configurable inside `docker-compose.yml` and ensures that our
Postgres database doesn't vanish across restarts and stuff.

Our EC2 instance will have the Docker daemon installed on it. When we are
deploying we will run `docker build` (from one of the CodeDeploy hooks)
and then `docker run`. The run command needs to forward a bunch of
environment variables to the container.

We should make sure that our EC2 instances always have Docker installed as
standard, because this is the minimum requirement to get everything else
fired up automatically. The idea of having most of our infra defined
statically in Dockerfile is to avoid dependence on things that are
outside the repo, which can lead to things being hard to reproduce. So
we want the EC2 instance to have minimal config outside of the Docker
containers. [This page](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html)
explains a couple of options for automatically configuring the launch
behaviour of instances.

Docker Compose files can be composed. We should have a `docker-compose.yml`
which is the base configuration, suitable for local development. In
production, we can run `docker compose -f docker-compose.yml -f production.yml up -d` which updates the base config with production-specific
changes defined in `production.yml`. These changes will be:

- remove volume bindings for application code (we should figure out how to bind
  the volumes where our code is being changed, because I think this allows
  us to make the local deployment nice and responsive; we basically want
  to emulate the local development environment where we run `yarn dev` and
  equivalent, but have all the applications running in the containers
- binding to different ports on the host
- nginx.conf uses the real `hitsave.io` domain name
- environment variables set differently
- different restart policy (`restart: always`) to help avoid downtime
- log aggregator?
  [See here](https://docs.docker.com/compose/production/)

## Postgres

We need to run the Sqlx migrations at some point during the deploy
phase, and if something goes wrong, we need to bail out.

One option is to build the migrations into the `hitsave` binary itself,
which can be done with [like this](https://docs.rs/sqlx/latest/sqlx/macro.migrate.html).

This feels a bit wrong, though - I think the migrations should happen
separately, and the main HitSave API binary just expects to connect to a
database in a valid state.

The alternatives are:

1. Have a Docker image for the deploy phase which gives us access to the
   Rust environment and `sqlx-cli`. We would then fire this container up
   from one of the CodeDeploy hooks, and run the `sqlx migrate run`
   script from there.
2. Create a small separate Rust binary, which basically has the
   `sqlx::migrate!()` in it as a one-liner.

Option 2 is the best one - we can have nice fine-grained control over
what happens at migration time if we ever need it to become more
complex for some reason.

Our plan to have Postgres in the `docker-compose.yml` seems somewhat
unscalable for now. When we deploy a new version of the service, we
can't do blue/green deploys if the new Postgres instance is trying to
load up the same data files (I don't think two Postgres instances can be
serving the same PGDATA directory). OR: because the Postgres container
is likely to be very stable (i.e. will hardly change the Docker-level
config for it, only the data) there is probably just a way to restart the
other containers with docker commands. Yes: [see here](https://docs.docker.com/compose/production/).

## EBS (Elastic Block Storage)

This is the persistent storage attached to EC2 instances. The main
thing to be aware of is that if you 'terminate' an instance, it means
you are deleting it forever and all the EBS storage gets chucked away
with it (unless you have a special option set). Normally, if you want to
take down an instance, you just want to 'stop' it, rather than 'terminate'.
When you 'stop', you don't pay for the instance, but the EBS storage
stays alive. You do pay for the EBS while the instance is stopped, of
course.

## Secrets

NOTE: I've done a lot of reading about this and not arrived any final
conclusions about how to do it. There's a lot to consider and lots of
options... This needs to be an open issue for now.

We need to get a load of secrets into the EC2 instance so the API
binary can load them up when it starts. This includes things like the
GitHub client secret for authenticating against the GitHub API (which we
use for user sign-ups), as well the S3 secrets for accessing BLOBs.

AWS has a secrets management service, but it's very expensive and I
think overkill for us. It does seem like storing secrets in environment
variables is a bad idea though, so we should avoid it. We would need to
configure the application code to load secrets from files or some other
way.

I actually think the best way to deal with this
is to just SSH into the instance and mess with the secrets manually
whenever we need to. I would then have the real life secrets saved in my
1Password account which I believe to be very secure. I would also store
the SSH key in there. Then the security of the HitSave company relies on
my 1Password account, which is fine. We should also try to remember to
rotate secrets semi-regularly and all that jazz.

Note that if you load secrets into Docker environment variables, then
they are accessible in the container's image file.

The best way is to use the Docker Secrets functionality. You can define
which files the secrets are stored in on the host machine in your `docker-compose.yml`
and it will securely load them into `/run/secrets` in the relevant
containers, without exposing the values anywhere in the Docker image.

## Organizing everything

I think there's merit to having a new directory in the monorepo `xyz`
called deploy. In here, we will have all the Dockerfiles, docker compose
yml, the shell scripts we need to run etc. This subdirectory is the one
which gets loaded into the EC2 container by CodeDeploy, along with the
build artifacts from S3 (which got put there by GitHub).

## Local development

- /etc/hosts configuration
  - Now that the whole app runs as a unified whole in a collection of
    Docker containers, it would also be nice to set things up to emulate
    proper host names without ports, rather than having to deal with
    things like `http://localhost:3000` in the browser all the time.
  - To set this up, edit `/etc/hosts` to include the following lines:
    ```
    127.0.0.1 hitsave-local.io
    127.0.0.1 www.hitsave-local.io
    ```
    You'll need to edit this as root.
  - nginx is set up to correctly forward traffic from subdomains `api`
    and `web` to the relevant Docker containers and port numbers.

# Todos when deploying the real HitSave

- Set up a production EC2 instance
- Set up an instance profile, with a role that includes the CodeDeploy
  policy
- Connect CodeDeploy to hitsave-io org
- Create a CodeDeploy user, also with CodeDeploy permissions
- Use a production environment, and give this the secret credentials for the
  CodeDeploy user
- Include the GitHub action for CodeDeploy and the appspec file
- Set up an S3 bucket for build artifacts
