# Status page integration

What the control component publishes, and what a consumer has to be careful about.

**Endpoint:** `http://<node>/service/control/status` — note `/service/`, singular. Control rewrites this file once a minute.

The node reports facts about itself. **It does not decide whether they are good or bad** — the page owns that judgement. The one exception is `Status` and `Error`, which carry control's own summary of what it found.

---

## Fields worth rendering

### `Payload.Identity`

```json
{
  "NodeAddress": "0x481029997EFfD67A74b48C98D763e2a2147e68A6",
  "EthAddress": "",
  "Registration": "unregistered"
}
```

A node installation establishes only a **node address**. Its pairing to an **eth address** (the guardian identity) happens on chain, and control resolves it by matching the node address against `CurrentTopology` in the ethereum-reader status.

`Registration` has **three** values, and the third one matters:

| value | meaning |
|---|---|
| `registered` | found in the topology; `EthAddress` is populated |
| `unregistered` | genuinely absent from the topology |
| `unknown` | the topology could not be read or parsed |

`unknown` is not `unregistered`. One says "this node is not on chain", the other says "we could not tell". Rendering the second as the first is a claim the data does not support.

**All three v5 nodes are `unregistered` today.** That is correct output, not a loading state.

### `Payload.Services[]`

Per running component:

```json
{
  "Name": "ethereum-reader",
  "ImageTag": "lukerogerson1/management-service:v2.7.1-immediate",
  "ImageDigest": "sha256:0ed28c67738ca1d3ded50c30..."
}
```

Show **`ImageTag` plus a shortened `ImageDigest`**. Two components can run the same tag name with different content — `ethereum-reader` and `matic-reader` both run a tag called `v2.7.1-immediate` from different repos, with different digests. Showing the digest is the entire point; do not group or dedupe by tag.

**Ignore `Services[].Image`.** On these nodes it is byte-identical to `ImageDigest`, because they use the containerd-backed `overlayfs` store where the image ID *is* the manifest digest. `ImageDigest` is the semantically correct field and stays correct on a node using the older `overlay2` driver, where the two genuinely differ.

`ImageTag` is read from the **running container**, not from the compose file, so it is what is actually running. After a partial update the two can legitimately disagree, and that disagreement is real.

### `Payload.ImageDrift[]`

Lists **only** components whose running image does not match what the compose file resolves to. A component absent from this array is up to date.

```json
{
  "Service": "nginx",
  "Image": "nginx:latest",
  "Running": true,
  "ContainerOutdated": false,
  "ImageOutdated": true,
  "LocalDigest": "sha256:341bf0f3...",
  "RegistryDigest": "sha256:abe47724..."
}
```

- `ContainerOutdated` — the container still runs a previous image after a pull
- `ImageOutdated` — the image on disk is behind the registry

`RegistryDigest` is refreshed **every six hours**, because registry reads count against Docker Hub's anonymous pull rate limit and the poll runs every minute. Do not present it as real-time. An **empty** `RegistryDigest` means the registry could not be reached: that is unknown, not up to date.

### `Payload.StaleComponents[]`

Lists **only** components not reporting freshly. Absent means fresh.

```json
{ "Service": "vm-lambda", "Timestamp": "2026-05-17T13:30:58.910Z", "AgeSeconds": 11732220, "State": "stale" }
```

`State` is `stale` (older than 10 minutes) or `unknown` (no status file, or a timestamp that could not be parsed).

**Call it "status stale", not "down".** They are different, and the fleet currently has one of each:

- `ethereum-writer` on t2 and t3 — genuinely hung, no log output since June and May
- `vm-lambda` on all three — working perfectly, transactions succeeding, simply not refreshing its status file

A stale timestamp means *"we cannot tell"*, not *"it is dead"*.

Components that write no status file at all are excluded, so nginx will never appear here. The expectation comes from the compose file: a component that mounts a status directory is expected to write one.

### `Payload.Metrics.Disks[]`

```json
{ "Mountpoint": "/", "Fstype": "ext4", "UsedPercent": 43.5, "TotalMbytes": 30672.9, "UsedMbytes": 13345.1 }
```

**Filter on `Fstype` before showing or alerting on anything.** Six of the nine mounts on these nodes are `squashfs` snap images sitting at 100% by design, forever. Skip `squashfs`, `iso9660`, `tmpfs`, `devtmpfs`, `overlay` and `ramfs`. In practice `/` is the mount that matters.

Control already warns at 80% and escalates at 90% into `Status` and `Error`, so the page does not have to duplicate that logic — but it must not render the snap mounts as nine disks, six of them full.

### `Payload.Updater`

```json
{
  "Branch": "feature/v5-ready",
  "AppliedCommit": "73a5b9e...", "AppliedAt": "2026-10-01T10:43:15.123Z",
  "CheckedOutCommit": "73a5b9e...",
  "RunningCommit": "fda624c...",
  "TargetCommit": "73a5b9e...",
  "State": "idle",
  "ScheduledFor": 0,
  "UpdatesDisabled": false,
  "LastAttemptAt": "...", "LastSuccessAt": "...",
  "LastError": "", "ConsecutiveFailures": 0
}
```

Everything about updating, as fields rather than prose. Before this the only way to answer "is this node up to date" was to parse the joined `Status` string.

`State` is one of:

| | |
|---|---|
| `idle` | applied, nothing to do |
| `behind` | the target commit is not the applied one; it will update on a following tick |
| `scheduled` | waiting for this node's slot in a staggered rollout — see `ScheduledFor`, a unix timestamp |
| `failing` | the last update failed; see `ConsecutiveFailures` and `LastError` |
| `disabled` | `DONT_UPDATE` is set on the node |
| `unknown` | no poll has completed yet in this process |

**`ConsecutiveFailures` is the field to watch.** A failed update never records the commit, so the node retries every minute, in a fresh process each time. This counter is persisted on the node precisely so that a node which has failed two thousand times running does not look identical to one that failed once. Anything above a handful means a node that is stuck and will stay stuck.

**`RunningCommit` is not the same as `CheckedOutCommit`, and that is not a bug.** An update is carried out by the updater code from the *previous* commit, because control is a fresh process each tick started from whatever was checked out at the time. They differ on exactly the tick that applies an update. Showing both is what makes "a fix was shipped and nothing happened" diagnosable.

`AppliedCommit` is the update that ran all the way through; `CheckedOutCommit` is what the working copy is sitting at. They differ when a checkout landed but the update then failed, which is the case `ConsecutiveFailures` is counting.

There is no `updating` state. An update holds the poll lock for its whole duration and the status file is written after the poll finishes, so nothing writes a status *during* one — `Timestamp` simply stops advancing until it completes. A node mid-update looks like a node whose status has gone stale, and for a long update that is the honest reading.

### `Payload.Poll`

```json
{ "ConsecutiveSkips": 0, "TotalSkips": 0, "LastSkipAt": "", "LongestHeldSeconds": 0, "Kills": 0 }
```

Control runs from cron once a minute, and a poll that is still running when the next tick fires makes that tick skip rather than start a second one on top of it. This block says how often that has happened.

**All zeroes is the normal, healthy state** and will be what you see almost always. It means every poll finished before the next one started.

| Field | Meaning |
|---|---|
| `ConsecutiveSkips` | skips in an unbroken run, cleared the moment a poll takes the lock. **This is the one that says whether something is wrong right now.** |
| `TotalSkips` | never cleared, so it survives the problem passing |
| `LastSkipAt` | UTC, trailing `Z` |
| `LongestHeldSeconds` | the longest hold ever observed on this node, not the most recent |
| `Kills` | times a poll was held past 20 minutes and had to be killed |

A handful of skips is unremarkable — an update that builds images from source takes most of a minute, so a tick skipping during one is the mechanism working. A *rising* `ConsecutiveSkips` is the signal: it means one poll has been running for that many minutes.

`Kills` stops rising after three by design. The shell caps it and then reports instead of killing, so that a poll which is slow rather than stuck is not killed and restarted forever. **`Kills` at the cap with `ConsecutiveSkips` still climbing is a node that needs a human** — it is stuck, and the node has already stopped trying to fix itself.

This is recorded by `run-control.sh`, not by control. Control only ever runs while holding the lock, so from the inside it would always see "held by me" and could never see a tick it did not run.

### `Status` and `Error`

`Status` is control's own summary, entries joined with `, ` and each prefixed `• `. Individual messages never contain a comma, so splitting on `, ` is safe.

`Error` is empty when nothing is wrong. It is claimed by the most specific problem available — a failed update outranks a filling disk.

---

## Things that will bite you

### Clock skew

`AgeSeconds` in `StaleComponents` is computed **on the node**, by the same clock that wrote the file, so it is unaffected by any difference between the node's clock and the browser's.

If you compute ages yourself from each component's own `Timestamp`, you are comparing the node's clock against the browser's. With a 10-minute threshold and NTP-synced hosts that is immaterial, but **prefer `AgeSeconds` where control provides it** — it is the more trustworthy number.

The same applies to the top-level `Timestamp`: it says when the node wrote the file, not when you fetched it. Showing "updated N seconds ago" from it mixes two clocks.

### Timestamp precision is not consistent

Components write different fractional-second precision:

```
2026-09-29T13:25:01.776Z            milliseconds   most components
2026-09-29T13:25:24.044297Z         microseconds   vm-l3-dummy-service
2026-09-29T13:25:15.347422897Z      nanoseconds    signer, vm-verifier
```

Truncate the fraction to 3 digits before parsing rather than trusting a date parser with 9 of them. All are UTC and marked with a trailing `Z`; a value without an offset is UTC, not local.

### Empty never means OK

An empty `EthAddress`, `RegistryDigest` or `ImageDigest` means *not known*. Render it as unknown. Treating a missing value as a passing check is how a broken signal looks healthy — which is the bug that started this whole piece of work.

### Do not compare docker tags against self-reported versions

Each component reports a version about itself (`Payload.Version.Semantic` on its own endpoint). **That is not comparable to its docker tag.** They are different naming schemes, and comparing them produced months of false "behind" markers on nodes that were entirely up to date:

| component | docker tag | self-reported |
|---|---|---|
| ethereum-writer | `v1.7.3-main` | `v1.7.1-immediate` |
| vm-notifications | `v1.0.31` | `v1.0.3-cebec9d5` |
| ethereum-reader | `v2.7.1-immediate` | `base-d751eae2` |

All of those are running current images. Use `ImageDrift` for staleness — it compares digests and is authoritative. Show the self-reported version as information if it is useful, never as a freshness signal.

### Expect real findings immediately

These are correct output, not bugs in your implementation:

- `vm-lambda` stale on all three nodes, 135–159 days
- `ethereum-writer` unhealthy on t2 and t3 — genuinely hung since June and May
- `vm-l3-dummy-service` and `vm-verifier` unhealthy everywhere — their healthcheck is `ping -c 1 logger` and their images ship no `ping`, so it is a false negative
- all three nodes `unregistered`
