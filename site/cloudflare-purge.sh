#!/bin/sh
# Runs when the container starts (nginx runs /docker-entrypoint.d before serving). Cloudflare keeps the site at its
# edge (a cache rule, 2026-11-18), so after a deploy it would go on serving the old pages: once this container is
# serving, purge every file a deploy can change in place, and again a minute later in case the old container answered
# in between. The hashed /assets/ are left alone (they never change, and a tab still open on the old build needs its
# chunks). A page is purged under each address it answers to. Needs CLOUDFLARE_CACHE_TOKEN in the service's environment
# (Zone Read and Cache Purge on this zone only); without it nothing happens. The token never reaches the output or argv.
[ -n "$CLOUDFLARE_CACHE_TOKEN" ] || { echo "cloudflare purge: no token, skipped"; exit 0; }
site=https://anthonymuniz.dev
urls=$(cd /usr/share/nginx/html && find . -type f ! -path './assets/*' | sed 's#^\./##' | while read -r f; do
  echo "\"$site/$f\""
  case "$f" in
    index.html) echo "\"$site/\"" ;;
    */index.html) d=${f%index.html}; echo "\"$site/$d\""; echo "\"$site/${d%/}\"" ;;
  esac
done | tr '\n' ',' | sed 's/,$//')
cf() { printf 'Authorization: Bearer %s\n' "$CLOUDFLARE_CACHE_TOKEN" | curl -fsS -m 20 --retry 3 --retry-delay 5 -H @- "$@"; }
(
  sleep 10
  zone=$(cf "https://api.cloudflare.com/client/v4/zones?name=anthonymuniz.dev" | grep -o '"id":"[0-9a-f]\{32\}"' | head -1 | cut -d'"' -f4)
  for pause in 0 60; do
    sleep "$pause"
    if [ -n "$zone" ] && cf -o /dev/null -X POST -H "Content-Type: application/json" --data "{\"files\":[$urls]}" \
      "https://api.cloudflare.com/client/v4/zones/$zone/purge_cache"; then
      echo "cloudflare purge: done"
    else
      echo "cloudflare purge: failed"
    fi
  done
) &
