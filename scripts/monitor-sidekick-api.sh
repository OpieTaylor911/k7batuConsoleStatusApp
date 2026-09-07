#!/usr/bin/env bash
# Samples API latency and gpspipe process count to confirm no leak / no slowdown.
set -u
for i in $(seq 1 6); do
  n=$(pgrep -c gpspipe 2>/dev/null || echo 0)
  t=$(curl -s -o /dev/null -m 10 -w '%{http_code} %{time_total}s' http://127.0.0.1:8080/api/sidekick)
  echo "sample $i: gpspipe_procs=$n  api=$t"
  sleep 4
done
