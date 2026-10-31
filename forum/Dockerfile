# Science Claw forum. Build from the repo root:  docker build -f forum/Dockerfile -t claw-forum .
# Persist /data (SQLite) with a volume. Deployed to Fly.io with forum/fly.toml.
FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production FORUM_PORT=8080 FORUM_DB=/data/forum.db NODE_OPTIONS=--no-warnings
COPY forum/ ./forum/
RUN mkdir -p /data && chown node:node /data
USER node
EXPOSE 8080
VOLUME ["/data"]
CMD ["sh", "-c", "node forum/seed.mjs && node forum/server.mjs"]
