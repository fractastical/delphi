# Hosted delphisci MCP server (Streamable HTTP on :8080/mcp). Deployed to Fly.io by
# .github/workflows/deploy-mcp.yml; .dockerignore limits the context to what the server reads.
FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production DELPHI_HTTP_PORT=8080
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY . .
USER node
EXPOSE 8080
CMD ["node", "mcp/server.mjs"]
