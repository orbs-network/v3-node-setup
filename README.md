# v3-node-setup

Everything needed to install and run an Orbs L3 validator node, and to keep it updated
and observable once it is running.

A node is a Docker Compose stack plus one host process. This repo holds four things, and
they are separable:

| Component | Lives in | Runs as |
|---|---|---|
| [Installer](#installer) | `install.sh`, `scripts/`, `setup/` | one-shot, as root |
| [Updater](#updater) | `control/src/updater.py` | inside control's cron tick |
| [Control](#control) | `control/src/` | host process, root's crontab, once a minute |
| [Logger](#logger) | `logging/` | container in the compose stack |

Supporting pieces: `docker-compose.yml` (the stack and the update descriptor),
`nginx/conf.d/default.conf` (the single HTTP surface), `.env.template`.

## The fleet

Three v5 validators: `v5-t1-us-e2`, `v5-t2-us-e2`, `v5-t3-us-e2`. Each has the repo
checked out at `/opt/orbs/v3-node-setup` on branch `feature/v5-ready`. t1 is where we
watch and SSH first.

## HTTP surface

Everything is served on port 80 by the `nginx` container.

| Path | Serves |
|---|---|
| `/service/<name>/status` | `.data/<name>/status.json`, as a static file |
| `/service/<name>/logs` | that container's Docker logs, proxied to `logger` |
| `/service/{control,updater,recovery}/logs` | `.data/<name>/log.txt`, as a static file |
| `/service/vm-<name>/<path>` | proxied into the `vm-<name>` container |

Note the singular `/service/`, and note that a component's status is at
`/service/<name>/status`, **not** `/status`.

The logger upstream goes through a variable (`set $logger_upstream logger;`) rather than a
literal hostname, and that is deliberate — see the comment next to it. nginx resolves a
literal name in `proxy_pass` once at configuration load and caches it for the life of the
process, so the logger being recreated with a new address left every log request 404ing
for a day (#70). Only a variable re-resolves. An `upstream` block does not fix it either.

Three legacy names are rewritten: `/services/…` → `/service/…`,
`/service/management-service/…` → `/service/ethereum-reader/…`, and
`/service/logs-service/…` → `/service/logger/…`. A fourth, `/service/boyar/…` →
`/service/control/…`, is configured but does not work — issue #41.

Location order in `default.conf` is load-bearing: the `status` and `logs` locations are
declared before the `vm-*` proxy block, so `/service/vm-lambda/status` serves the status
file rather than proxying into the container. The static `control|updater|recovery` log
alias is declared before the `logger` proxy for the same reason.

---

# Installer

`install.sh` → `scripts/run.sh` → `scripts/install-dependencies.sh`,
`scripts/prompt_and_env.py`, `scripts/install-control-cron.sh`.

One-shot, run as root. Ubuntu only on Linux; macOS gets a reduced path
(`scripts/run-macos.sh`) that sets up `.env` and keys and nothing else.

## Running it

```bash
curl -sSL "https://github.com/orbs-network/v3-node-setup/raw/main/install.sh?t=$(date +%s)" -o /tmp/install.sh && sudo bash /tmp/install.sh
```

Download first, then run under `sudo` — piping into `bash` leaves no TTY, which silently
skips the prompts (see below).

A different branch, which is how the v5 nodes are installed:

```bash
curl -sSL "https://github.com/orbs-network/v3-node-setup/raw/feature/v5-ready/install.sh?t=$(date +%s)" -o /tmp/install.sh && sudo BRANCH=feature/v5-ready bash /tmp/install.sh
```

Environment overrides: `BRANCH` (default `main`), `INSTALL_DIR` (default
`/opt/orbs/v3-node-setup`), `REPO_URL`.

Re-running on an existing install fetches and pulls the branch rather than recloning, and
skips the key prompts if `.env` already has a `NODE_PRIVATE_KEY`.

## What it asks for

- **Node key** — press Enter to generate a new secp256k1 key, or paste an existing
  private key (64 hex, optional `0x`).
- **Guardian name** and **Guardian website**.

## What it creates

- The clone at `$INSTALL_DIR`, checked out on `$BRANCH`.
- `.env`, copied from `.env.template` and then filled in with `NODE_PRIVATE_KEY`,
  `NODE_ADDRESS`, `BASE_DIR` and `DOCKER_COMPOSE_FILE`.
- `scripts/keys.json` — `{node-address, node-private-key}`, both unprefixed. The address
  is stored in EIP-55 mixed case; `NODE_ADDRESS` in `.env` carries no `0x` prefix, and
  control adds one when reporting it.
- `scripts/venv` — the installer's own Python venv (`coincurve`, `eth-hash`), used only
  for key generation. This is **not** control's venv.
- A root crontab entry for control (see [Control](#control)).
- `.data/<component>` directories for the components that mount one.
- The running stack, via `docker compose up -d`.

Dependencies it installs on Ubuntu when missing: build tools (`build-essential`,
`autoconf`, `automake`, `libtool`, `pkg-config`), Docker via `get.docker.com`, Docker
Compose (standalone v2.30.2, or a `/usr/local/bin/docker-compose` shim onto `docker
compose`), and `python3`/`python3-venv`/`python3-pip`.

## What it does NOT do

This is the part that surprises people.

- **It never learns, stores or verifies an eth address.** A node installation establishes
  only a *node address*. The eth address is the guardian identity, and it is coupled to
  the node address **on chain**, by a human on a web page, never during installation.
  Nothing in this repo learns which Ethereum account was used. See issue #65.
- **Guardian name and website are prompted and then discarded.** They are not written to
  `.env`. Their only use is to build a registration URL:
  `https://guardians.orbs.network?name=…&website=…&ip=…&node_address=…`, printed once,
  mid-install, before the cron and compose output scrolls it away. Nothing writes it to a
  file, and a re-run with a key already present never prints it again.
- **It does not verify registration.** An unregistered node installs, starts and runs
  indefinitely looking entirely healthy. All three v5 nodes are unregistered today, and
  control reports that correctly as `Registration: unregistered`.
- **It does not create control's venv.** `control/.venv` is created lazily by
  `scripts/run-control.sh` on the first cron tick.

### No TTY means no prompts

If there is no TTY — `curl … | sudo bash`, or any non-interactive context —
`prompt_and_env.py` returns immediately: no key, no `.env` values, no registration URL.
The rest of the install proceeds, so you end up with a started stack and no node key.
Fix it afterwards with:

```bash
sudo /opt/orbs/v3-node-setup/scripts/venv/bin/python3 /opt/orbs/v3-node-setup/scripts/prompt_and_env.py
```

### Stale bits

`setup/` contains only `config.json`, which nothing reads. `Dockerfile` in the repo root
builds an Ubuntu image used by the `smoke-test` CI workflow, and that workflow still
invokes `setup/install.sh`, which no longer exists — it runs only on PRs to `main`, so
nobody has been tripping over it on `feature/v5-ready`.

---

# Updater

`control/src/updater.py`. Not a separate process: it runs inside control's once-a-minute
cron tick, when control is invoked as `poll`.

Git is the deployment mechanism. The node follows a branch, and a commit on that branch
is a deployment.

## The update descriptor

The thing that drives updates is a commented-out YAML block at the top of
**`docker-compose.yml` on the remote branch**, between
`# ---- UPDATE-DESCRIPTOR-BEGIN ----` and `# ---- UPDATE-DESCRIPTOR-END ----`. It is read
with `git show <ref>:<path>`, never from the local working copy.

Which ref and path is set by `DOCKER_COMPOSE_REMOTE_GIT_PATH`, e.g.
`origin/feature/v5-ready:docker-compose.yml`. There is deliberately no default — an unset
value raises immediately rather than failing later with a confusing "descriptor section
not found".

Every line in the block is prefixed `# ` so the compose file stays valid; the updater
strips exactly one `# ` per line before parsing. A line written `# # …` therefore parses
as a genuine YAML comment. That is how the inline documentation in the block survives.

Fields:

| Field | Meaning |
|---|---|
| `targetNodes[].id` | node addresses this applies to; `*` means all. Both sides are normalised, so prefix and casing do not matter |
| `updateInAction` | master switch. False means no node updates |
| `updateMode` | `immediate`, or `scheduled` |
| `updateResolution` | minutes to spread a scheduled rollout across |
| `commit` | a commit hash, or `latest` to resolve the branch tip |

Under `scheduled`, each node hashes its own node address to pick a deterministic minute
within the window, anchored on the target commit's own timestamp — so the fleet rolls out
staggered but reproducibly, and a node that is not yet due reports
`Extra: {"status": "updating", "time": <unix>}`.

## What applying an update does

`trigger_update()`, in order:

1. Bail out if `DONT_UPDATE=true`.
2. Read `DOCKER_COMPOSE_FILE` **before** touching the checkout, so a missing setting fails
   before the working copy has been moved halfway.
3. `git fetch origin`.
4. Report any local modifications to tracked files. A node is a deployment target, not
   somewhere to edit, so a modified tracked file is itself the anomaly worth surfacing —
   and the checkout is about to discard it.
5. `git checkout -f -B <branch> <commit>`. `-B` keeps the working copy **on the branch**
   rather than detached, so the state is legible to whoever logs in next. `-f` discards
   local edits rather than stashing them; stashing used to leave a stash entry behind on
   every single update and never dropped one.
6. Check disk headroom (`MIN_FREE_DISK_GB`, default 5). A pull downloads new images while
   the old ones are still on disk, so pulling without headroom can fill the filesystem and
   take the node down. If short, prune dangling images and re-check; still short, raise.
7. `docker compose pull`.
8. `docker compose up -d --remove-orphans`.
9. `docker image prune -f` — dangling only, never `-a`: an untagged image can still be the
   one a stopped container needs.
10. Record the commit in `.data/control/applied_commit.json`.

## Non-obvious behaviours

**Images are pulled only inside `trigger_update()`, never on a poll.** This is deliberate
and must stay that way. Upstream images use mutable tags, so pulling on every poll would
mean an upstream re-push could restart production validators with no commit, no review and
no record. Promotion of a git commit is the only thing allowed to move images.

**A commit is applied by the *previous* commit's code.** Control is a fresh process on
each cron tick, started from whatever is checked out at that moment. So a change to
`trigger_update` merged as commit N is not what applies commit N — the code at N-1 does
that. It stays dormant until commit N+1 triggers the next update. Plan two commits when
changing the apply path, or exercise it on t1 alone first.

**Checked out is not applied.** The checkout happens before compose runs, so a compose
failure leaves the working copy sitting at the target commit while nothing was actually
applied. `applied_commit.json` records the commit whose update ran all the way through,
and the two are compared separately — without it a half-failed update reported itself as
up to date forever. On the first poll after this check was introduced there is no marker,
so the updater *adopts* whatever is checked out rather than forcing a restart of every
node's services to tell us something we can already see.

**`git ls-remote` ambiguity is an error, not a guess.** It exits zero and prints nothing
when a branch does not resolve, and prints several lines when a name is ambiguous. Both
are raised rather than taking the first field.

**Branch parsing strips only the remote name.** `origin/feature/v5-ready` → `feature/v5-ready`.
Keeping only the last path segment used to turn that into `v5-ready`, which git matched by
trailing component right up until two branches shared a final segment.

## Manual control

- `DONT_UPDATE=true` in `.env` — the node polls, reports, and refuses to apply anything.
- `updateInAction: false` in the descriptor — nothing in the fleet updates.

---

# Control

`control/src/`: `main.py` (entry point), `system_monitor.py` (what to report),
`image_drift.py`, `staleness.py`, `identity.py`, `config.py`, `utils.py`, `logger.py`.

A host process, not a container. It has to be, since it drives `docker compose`.

## How it runs

Root's crontab, once a minute:

```
* * * * * /opt/orbs/v3-node-setup/scripts/run-control.sh poll >> /opt/orbs/v3-node-setup/.data/control/log.txt 2>&1
```

Installed by `scripts/install-control-cron.sh`, which is idempotent and replaces any
previous `run-control.sh poll` line.

`scripts/run-control.sh` is the wrapper. Each tick it:

- Sources `.env` and exports `BASE_DIR` and `DOCKER_COMPOSE_FILE`.
- Rotates `.data/control/log.txt` if it is over `LOG_MAX_BYTES` (default 10MB), keeping
  `LOG_KEEP` (default 3) generations. This exists because the log reached **969MB** on a
  node before anyone noticed. Rotating by rename is safe here precisely because cron
  opens the file fresh each run, so nothing holds a descriptor across ticks.
- Creates `control/.venv` (Python 3.12 on the nodes) if missing, and reinstalls
  `control/requirements.txt` whenever its sha256 differs from the marker stored *inside*
  the venv. Installing only on venv creation meant a new dependency never reached an
  existing node, and control then failed to import it once a minute, forever. The marker
  is written only after a successful install, so a failure is retried next tick.
- Runs `control/src/main.py` with whatever arguments it was given.

`poll` is the only argument cron passes, and the only one that runs the updater. Running
`run-control.sh` with **no** argument also issues a `docker compose up -d` (this is what
`make control` does); `make control-poll` is the cron-equivalent.

## What it publishes

One file, rewritten every tick: `.data/control/status.json`, served at
`http://<node>/service/control/status`.

The consumer-facing contract is documented in
**[STATUS_PAGE_INTEGRATION.md](STATUS_PAGE_INTEGRATION.md)** — read that before building
anything against the endpoint. In brief:

- `Timestamp`, `Status`, `Error`, `Extra`
- `Payload.Version.Semantic` — `<git commit> / <tag or "untagged">`
- `Payload.Identity` — `NodeAddress`, `EthAddress`, `Registration`
- `Payload.Metrics` — CPU, memory, uptime, `Disks[]`, `Processes[]`
- `Payload.Services[]` — one entry per running container, including `ImageTag` and
  `ImageDigest` read from the **running container**, not from the compose file
- `Payload.ImageDrift[]` — only the services that have drifted
- `Payload.StaleComponents[]` — only the components not reporting freshly

Other files under `.data/control/`: `log.txt` (+ `.1`…`.3`), `applied_commit.json`,
`image_drift.json` (the registry digest cache).

## What each check does

**`identity.py`** resolves the eth address. A node knows only its own node address; the
coupling to an eth address happens on chain, so it is read back from `CurrentTopology` in
`.data/ethereum-reader/status.json`, matching on `OrbsAddress`. `Registration` is
`registered`, `unregistered` or `unknown` — and `unknown` means the topology could not be
read, which is not the same as being absent from it.

**`image_drift.py`** compares three things per compose service: the image the compose file
asks for, the image on disk, and the digest the registry currently serves. Two different
failures:

- `ContainerOutdated` — a pull landed but the container was never recreated.
- `ImageOutdated` — the image on disk is behind the registry. Nothing local can see this,
  because the upstream tags are mutable and get re-pushed. This is why the nodes ran
  three-year-old builds for months while every local signal said the tags matched.

Registry reads count against Docker Hub's anonymous pull rate limit, so remote digests are
cached and refreshed every `IMAGE_DRIFT_REFRESH_MINUTES` (default 360). A refresh only
counts as done once every image was read, so a transient registry failure is retried next
poll instead of being held for six hours. Services with a `build:` are skipped — there is
no registry image to compare against.

**`staleness.py`** reads each component's own `status.json` and reports how old its
`Timestamp` is. Docker only knows whether a process is alive; a container can sit at
`Up 6 months (healthy)` doing nothing. What a component last said about itself is the
better signal, and nothing was reading it.

Only components that **declare** they report are checked: declaring means mounting a
directory ending `/opt/orbs/status` in the compose file. nginx mounts `.data` in order to
*serve* those files and writes none of its own, and holding it to a contract it never
entered would leave a permanent unknown that people learn to skip.

Threshold is `STATUS_STALE_AFTER_MINUTES` (default 10) for every component, whatever its
own tick interval — a component that cannot meet it is a bug to fix, not an exception to
configure. Timestamp precision varies across components (milliseconds, microseconds and
nanoseconds all appear), so the fraction is truncated to 6 digits before parsing.

**Disk usage** warns at `DISK_WARN_PERCENT` (80) and escalates into `Error` at
`DISK_CRITICAL_PERCENT` (90). Pseudo filesystems are skipped — `squashfs`, `iso9660`,
`tmpfs`, `devtmpfs`, `overlay`, `ramfs`. Six of the nine mounts on these nodes are
squashfs snap images sitting at 100% by design, and alerting on those would fire on every
node forever, which is how a signal stops being read. `Error` is only claimed if nothing
more specific already holds it: a failed update says more than a filling disk does.

## Design rules that run through all of it

**Empty or unknown is never OK.** `Registration` has a third value, `unknown`. Image drift
records an empty `RegistryDigest` when the registry is unreachable, rather than claiming a
match. Staleness reports `unknown` rather than an age when the file or timestamp cannot be
read. Not knowing is a different thing from knowing it is fine, and conflating the two is
the bug that started this whole piece of work.

**The node reports facts; the status page owns comparisons.** Control does not decide
good or bad beyond the summaries it writes into `Status` and `Error`. In particular: a
component's self-reported version is not comparable to its Docker tag. They are different
naming schemes, and comparing them produced months of false "behind" markers on nodes that
were completely up to date.

**A check that cannot run must not take the poll down.** Drift and staleness both catch
broadly and return empty — a node that cannot check is still a node that should report its
metrics.

**`Status` is per-tick.** Control is a fresh process each minute, so the in-memory list
behind `Status` starts empty every tick and contains only what *this* tick found. It reads
`OK` when the tick found nothing. Entries are joined with `, ` and individual messages
never contain a comma, so splitting on `, ` is safe — which is why the drift and staleness
summaries join with ` | `.

**Logging is quiet by design.** The poll runs 1440 times a day, so routine progress is at
`DEBUG` and `INFO` is reserved for what actually happened. `LOG_LEVEL=DEBUG` gets the
detail back.

## Developing

```bash
cd control
make install     # venv + requirements
make test        # pytest
make lint        # pylint + flake8
make typecheck   # mypy
```

Tests live in `control/tests/` and run in CI on PRs to `main`
(`.github/workflows/control.yml`).

---

# Logger

`logging/`. A small TypeScript/Express service, the **only** service in
`docker-compose.yml` built from source (`build: ./logging`); everything else runs a pinned
image from a registry.

It mounts the Docker socket and exposes container logs over HTTP, read straight from the
Docker API. nginx proxies `/service/<container>/logs` to it.

Because it is built from source rather than pulled, the updater has to build it
explicitly — `pull` skips a service with a `build:` section and `up -d` reuses whatever
image is already on disk. Without that step a `logging/` change was checked out, recorded
as applied, and never actually ran (#71).

```
GET /service/<container>/logs
```

Returns `text/plain`. With no parameters you get the whole log, which is what this
endpoint has always done. The query parameters are Docker's own, passed through to the
daemon, so anyone who knows `docker logs` knows this endpoint.

| Parameter | Values | Meaning |
|---|---|---|
| `tail` | non-negative integer, or `all` (default) | only the last N lines |
| `since` | unix seconds, RFC3339, or a relative age like `15m` / `2h` | only entries after this point |
| `until` | same as `since` | only entries before this point |
| `timestamps` | `1/0`, `true/false` (default off) | prefix each line with its timestamp |
| `stdout` | `1/0`, `true/false` (default on) | include stdout |
| `stderr` | `1/0`, `true/false` (default on) | include stderr |

That is the complete set. A malformed value returns `400` naming the parameter rather
than being silently dropped; unknown parameters are ignored.

```bash
curl 'http://<node>/service/ethereum-writer/logs?tail=100'
curl 'http://<node>/service/vm-lambda/logs?since=15m&timestamps=1'
curl 'http://<node>/service/signer/logs?since=2026-09-30T10:00:00Z&until=30m'
```

Full detail in **[logging/README.md](logging/README.md)**. Worth knowing here:

- **`follow` returns `501`.** Streaming works server-side, but nginx buffers this location,
  so a followed stream would sit in nginx and never reach the client. Needs
  `proxy_buffering off`. Issue #83.
- **`head`, byte counts and `grep` are not supported.** None of them map to a Docker
  parameter, so they would have to be implemented locally, with early teardown of the
  upstream request and a cap on user-supplied patterns.
- **The response is streamed, not buffered.** A container keeps up to 150MB of logs
  (`50m` × `3`, set by the `x-logging` anchor in `docker-compose.yml`) and the daemon reads
  across the rotated files, so an unfiltered request can return all of it. Streaming makes
  that cost bandwidth rather than memory. A client that disconnects halfway tears down the
  daemon request too.
- **Docker's framing does not respect chunk boundaries.** `demux.ts` is a `Transform` that
  carries partial headers and payloads across chunks; decoding each chunk independently —
  which this service used to do — produced garbage for anything over one chunk.
- **Non-container components bypass this service entirely.** `control`, `updater` and
  `recovery` have their log files served statically by nginx, so none of the flags above
  apply to them. Issue #68.

Logger also writes its own `.data/logger/status.json` every 5 minutes, so it participates
in the same staleness contract as everything else.

---

# Healthchecks

Every `vm-*` service, plus `logger`, uses the same healthcheck: the component's own
`status.json` was written within the last 10 minutes.

```yaml
test: "test $$(( $$(date +%s) - $$(stat -c %Y /opt/orbs/status/status.json) )) -lt 600"
```

They previously all shared `ping -c 1 logger`, which tested nothing about the service and
passed or failed purely on whether the image happened to ship a `ping` binary.
`vm-verifier` and `vm-l3-dummy-service` sat permanently unhealthy on all three nodes for
months because theirs do not. Every red now means something — including `vm-lambda`, which
correctly fails this check (#67).

The `$$` is compose escaping for a literal `$`.

The Node components (`ethereum-reader`, `matic-reader`, `ethereum-writer`) use their own
`node healthcheck.js`; `signer` uses the healthcheck binary shipped in its image.

---

# Environment

`.env` lives at the repo root, is written by the installer from `.env.template`, and is
read both by `docker compose` and by `scripts/run-control.sh`.

| Variable | Used by | Notes |
|---|---|---|
| `NODE_PRIVATE_KEY` | signer, ethereum-writer | written at install |
| `NODE_ADDRESS` | most services, control | no `0x` prefix on disk |
| `ETHEREUM_ENDPOINT`, `MATIC_ENDPOINT` | readers, writer | RPC |
| `SIGNER_ENDPOINT` | ethereum-writer | |
| `BASE_DIR` | control | repo root; control resolves `.data/` from it |
| `DOCKER_COMPOSE_FILE` | control, updater | absolute path |
| `DOCKER_COMPOSE_REMOTE_GIT_PATH` | updater | `<remote>/<branch>:<path>`, **no default** |
| `DOCKER_SOCKET_PATH` | logger, vm-* | default `/var/run/docker.sock` |
| `DONT_UPDATE` | updater | `true` disables applying updates |
| `MIN_FREE_DISK_GB` | updater | default 5 |
| `DOCKER_DATA_ROOT` | updater | default `/var/lib/docker` |
| `IMAGE_DRIFT_REFRESH_MINUTES` | control | default 360 |
| `STATUS_STALE_AFTER_MINUTES` | control | default 10 |
| `DISK_WARN_PERCENT` / `DISK_CRITICAL_PERCENT` | control | default 80 / 90 |
| `LOG_LEVEL` | control | default `INFO` |
| `LOG_MAX_BYTES` / `LOG_KEEP` | run-control.sh | default 10MB / 3 |

---

# Known open issues

- **#67** — `vm-lambda` never refreshes its `status.json` timestamp. The service works
  fine; it has simply not said so since May. The fix belongs in the `vm-lambda` project.
- **#41** — nginx `boyar` → `control` routing does not work.
- **#68** — `control`, `updater` and `recovery` logs are served statically and support no
  flags at all. Parked deliberately.
- **#82** — nothing stops cron starting a second control process while an update is still
  running. An update that builds the logger takes most of the 60 second interval.
- **#83** — `follow` on the log endpoint, which needs `proxy_buffering off` in nginx.
- **#72–#80** — tidy-ups found while writing this README: test scaffolding on the readers,
  stale installer defaults, a dead `errors_file`, a broken smoke-test workflow, a shadowed
  `test.conf`. All verified, all low priority, all parked.

Closed on 2026-09-30, kept here because the lessons recur: **#70** (nginx caches a literal
`proxy_pass` hostname at load — only a variable re-resolves), **#81** (nothing reloaded
nginx, so config changes reached every node and never took effect), **#71** (the updater
never built the logger, so `logging/` changes never shipped). The pattern behind all three
is the same: a commit can be recorded as applied while part of what it changed is not
actually running. Check that a change took effect, not just that it deployed.
