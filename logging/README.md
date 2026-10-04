# v3-logging-service repo

## What's this?

A service to expose validator node container logs generically and flexibly.

## Reading logs

```
GET /service/<container>/logs
```

Returns the container's log as `text/plain`. With no parameters you get the
whole log, which is what this endpoint has always done.

The query parameters are Docker's own, passed through to the daemon, so if you
know `docker logs` you know this endpoint.

| Parameter | Values | Meaning |
|---|---|---|
| `tail` | non-negative integer, or `all` (default) | Only the last N lines |
| `since` | unix seconds, RFC3339, or a relative age like `15m` / `2h` | Only entries after this point |
| `until` | same as `since` | Only entries before this point |
| `timestamps` | `1/0`, `true/false` (default off) | Prefix each line with its timestamp |
| `stdout` | `1/0`, `true/false` (default on) | Include stdout |
| `stderr` | `1/0`, `true/false` (default on) | Include stderr |

```bash
curl 'http://<node>/service/ethereum-writer/logs?tail=100'
curl 'http://<node>/service/vm-lambda/logs?since=15m&timestamps=1'
curl 'http://<node>/service/signer/logs?since=2026-09-30T10:00:00Z&until=30m'
```

Unknown parameters are ignored. A malformed value returns `400` naming the
parameter rather than being silently dropped.

### Things worth knowing

- **`follow` is not supported** and returns `501`. Poll with `tail` instead.
  Streaming is in place server-side, but a live stream would need
  `proxy_buffering off` on this nginx location, which would unbuffer every
  other request through it as well, and each viewer would hold an open Docker
  log stream for as long as their tab was open. Decided against in issue #83.
- **`tail` is applied before the stream filter, by the daemon.** So
  `?tail=1&stderr=0` returns nothing if the very last line happened to go to
  stderr. That is Docker's behaviour, faithfully passed through, not a bug here.
- **`head`, byte counts (`tail -c`) and `grep` are not supported.** None of them
  map to a Docker parameter, so they would need to be implemented locally.
- **Non-container components** (`control`, `updater`, `recovery`) are served
  from here too, by reading their log files rather than the Docker API, but
  **only `tail` applies** to them. The rest of the parameters have no meaning
  for a file on disk and return `400` naming the one at fault rather than being
  accepted and ignored. `recovery` has a route but nothing writes its file, so
  it returns `404`. See the repo README for the detail (#68).

## Retention

Log volume is bounded by the Docker `json-file` driver, configured in
`docker-compose.yml`: `max-size: 50m` with `max-file: 3`, so up to ~150MB per
container. The daemon reads across the rotated files, so an unfiltered request
can return all of it. The response is streamed rather than buffered, so this
costs bandwidth and time but not memory — though `?tail=` is usually what you
actually want.
