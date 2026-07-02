# Zerg GTM Hub — static internal viewer.
# Caddy serves the dist/ bundle staged by build.py with HTTP basic auth.

FROM caddy:2.10-alpine

# Drop root before running Caddy (CWE-250 mitigation per semgrep).
# Caddy binds to 8080 (>1024) so it doesn't need root.
RUN adduser -D -u 10001 -h /home/caddyrun caddyrun \
 && mkdir -p /data /config \
 && chown -R caddyrun:caddyrun /data /config

COPY --chown=caddyrun:caddyrun Caddyfile /etc/caddy/Caddyfile
COPY --chown=caddyrun:caddyrun dist/ /srv/dist/

USER caddyrun
EXPOSE 8080

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
