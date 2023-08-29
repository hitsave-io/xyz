# Update TLS certs

1. SSH into EC2 instance
2. Unlike the notes I wrote last time, running `sudo certbot renew`
   didn't work because nginx was already bound to port 80 and certbot
   couldn't do it's nifty challenge thing.
3. So: `docker stop xyz-prod-nginx-1` - this causes some downtime for
   the app, which I think we can afford.
4. Now `sudo certbot renew` works.
5. Relaunch docker containers with `docker compose -p xyz-prod -f docker-compose.yml -f docker-compose.production.yml up -d`
