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

- **`follow` is not supported yet** and returns `501`. Streaming is in place
  server-side, but nginx buffers this location, so a followed stream would
  never reach the client. It needs `proxy_buffering off` in the nginx log
  location block. Tracked in issue #69.
- **`tail` is applied before the stream filter, by the daemon.** So
  `?tail=1&stderr=0` returns nothing if the very last line happened to go to
  stderr. That is Docker's behaviour, faithfully passed through, not a bug here.
- **`head`, byte counts (`tail -c`) and `grep` are not supported.** None of them
  map to a Docker parameter, so they would need to be implemented locally.
- **Non-container components** (`control`, `updater`, `recovery`) do not go
  through this service at all — nginx serves their log files statically, so
  none of the above applies to them. Tracked in issue #68.

## Retention

Log volume is bounded by the Docker `json-file` driver, configured in
`docker-compose.yml`: `max-size: 50m` with `max-file: 3`, so up to ~150MB per
container. The daemon reads across the rotated files, so an unfiltered request
can return all of it. The response is streamed rather than buffered, so this
costs bandwidth and time but not memory — though `?tail=` is usually what you
actually want.
