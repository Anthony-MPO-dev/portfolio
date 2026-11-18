#!/bin/sh
# Runs when the container starts (nginx runs /docker-entrypoint.d before serving). Cloudflare keeps the pages at its
# edge (a cache rule, 2026-11-18), so after a deploy it would go on serving the old build: once this container is
# serving, purge the zone's cache, and again a minute later in case the old container answered in between. Needs
# CLOUDFLARE_CACHE_TOKEN in the service's environment (Zone Read, Cache Rules and Cache Purge on this zone only);
# without it nothing happens. Never prints the token.
[ -n "$CLOUDFLARE_CACHE_TOKEN" ] || { echo "cloudflare purge: no token, skipped"; exit 0; }
(
  api=https://api.cloudflare.com/client/v4
  auth="Authorization: Bearer $CLOUDFLARE_CACHE_TOKEN"
  for pause in 10 60; do
    sleep "$pause"
    zone=$(curl -fsS "$api/zones?name=anthonymuniz.dev" -H "$auth" | grep -o '"id":"[0-9a-f]\{32\}"' | head -1 | cut -d'"' -f4)
    if [ -n "$zone" ] && curl -fsS -o /dev/null -X POST "$api/zones/$zone/purge_cache" -H "$auth" \
      -H "Content-Type: application/json" --data '{"purge_everything":true}'; then
      echo "cloudflare purge: done"
    else
      echo "cloudflare purge: failed"
    fi
  done
) &
