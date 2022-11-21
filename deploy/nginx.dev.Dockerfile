FROM nginx

COPY deploy/nginx.conf /etc/nginx/nginx.conf
ADD deploy/nginx/templates /etc/nginx/templates
