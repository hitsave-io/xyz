FROM node:19-alpine

COPY web/build build
COPY web/public public
COPY web/node_modules node_modules

CMD ["node", "./build/server.js"]
