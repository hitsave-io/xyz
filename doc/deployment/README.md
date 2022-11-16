# Deployment Docs

Since deployment is complicated, we need to maintain quite meticulous
records and documentation. The goal is to have both detailed
explanations of how and why things work the way they do, as well as
detailed human-readable records of the specific actions taken when
interacting with the production environments.

## Directory

- `/current`:
  - Documentation explaining the current state of deployments
- `/history`:
  - Records of actions taken to modify the deployment environment(s).
    This folder should consist of date-prefixed files (e.g.
    `20221116-initial-deployment.md`), which contain detailed explanations
    of the steps taken. This only applies to work which modifies the
    manually modifies the environment itself, not automatically
    initiated behaviour once the CI/CD pipeline is live and working as
    desired (so pushing to main to trigger a new deployment doesn't need
    an entry here).
