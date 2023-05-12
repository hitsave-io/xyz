# Update TLS certs

1. SSH into EC2 instance
2. Run `sudo certbot renew`
3. Relaunch docker containers with `docker compose -p xyz-prod -f docker-compose.yml -f docker-compose.production.yml up -d`
