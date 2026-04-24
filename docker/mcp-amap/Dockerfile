FROM node:20-slim

WORKDIR /app

COPY server/mcp-amap/package*.json ./
COPY server/mcp-amap/server.js ./server.js
COPY server/mcp-amap/healthcheck.js ./healthcheck.js

RUN npm ci --omit=dev

ENV NODE_ENV=production
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3100

EXPOSE 3100

CMD ["npm", "start"]
