"""Detects when the running containers no longer match the images the compose file asks for.

Two different things can drift, and they fail in different ways:

- The container can be older than the image already on disk, which happens when a pull
  succeeds but the container is never recreated.
- The image on disk can be older than the registry, which happens because the upstream
  tags are mutable and get re-pushed. Nothing local can see this, so it needs the registry.

The second one is why the nodes ran three-year-old builds for months while every local
signal said the tags matched.
"""

import json
import os
import time

import docker
import yaml
from docker import errors

from config import CONTROL_DIR
from logger import logger

# Reading a digest from the registry counts against Docker Hub's anonymous pull rate
# limit, so remote digests are refreshed on a slow cadence instead of every poll. The
# condition being watched for moves over months, so a stale reading costs nothing.
REGISTRY_REFRESH_SECONDS = int(os.getenv("IMAGE_DRIFT_REFRESH_MINUTES", "360")) * 60

cache_file = os.path.join(CONTROL_DIR, "image_drift.json")


def _load_cache() -> dict:
    """Returns the cached registry digests, or an empty cache if there are none"""

    try:
        with open(cache_file, encoding="utf8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    """Persists the registry digests so the next poll does not have to ask again"""

    try:
        with open(cache_file, "w", encoding="utf8") as file:
            json.dump(cache, file, indent=4)
    except OSError as error:
        logger.error("Could not persist the image drift cache: %s", error)


def compose_images(compose_file: str) -> dict[str, str]:
    """Returns the image reference each compose service expects, keyed by container name.

    Services built locally are skipped, since a `build:` has no registry image to compare against.
    """

    with open(compose_file, encoding="utf8") as file:
        compose = yaml.safe_load(file)

    images = {}

    for name, service in (compose.get("services") or {}).items():
        image = service.get("image")

        if not image:
            continue

        images[service.get("container_name", name)] = image

    return images


def registry_digests(client: docker.DockerClient, image_refs: list[str], now: float) -> dict[str, str]:
    """Returns the digest the registry currently serves for each image reference"""

    cache = _load_cache()
    digests = cache.get("digests", {})
    is_fresh = now - cache.get("checked_at", 0) < REGISTRY_REFRESH_SECONDS

    if is_fresh and all(ref in digests for ref in image_refs):
        return digests

    logger.info("Refreshing registry digests for %d image(s)", len(image_refs))

    refreshed = dict(digests)
    failed = False

    for ref in image_refs:
        try:
            refreshed[ref] = client.images.get_registry_data(ref).id
        except Exception as error:  # pylint: disable=broad-except
            # An unreachable registry must not fail the poll. Keep whatever was last known
            # and try again on the next refresh.
            logger.error("Could not read the registry digest for %s: %s", ref, error)
            failed = True

    # The refresh only counts as done once every image was read, so a transient registry
    # failure is retried on the next poll rather than held for the whole interval.
    _save_cache({"checked_at": cache.get("checked_at", 0) if failed else now, "digests": refreshed})

    return refreshed


def check(client: docker.DockerClient, compose_file: str) -> list[dict]:
    """Returns one record per compose service whose running image is not what compose asks for"""

    logger.info("Checking for image drift against %s", compose_file)

    expected = compose_images(compose_file)
    digests = registry_digests(client, sorted(set(expected.values())), time.time())

    drifted = []

    for container_name, image_ref in sorted(expected.items()):
        record = {
            "Service": container_name,
            "Image": image_ref,
            "Running": True,
            "ContainerOutdated": False,
            "ImageOutdated": False,
            "LocalDigest": "",
            "RegistryDigest": digests.get(image_ref, ""),
        }

        try:
            local_image = client.images.get(image_ref)
        except errors.ImageNotFound:
            # The compose file names an image that was never pulled, so the service cannot
            # be running what it should be.
            record["ContainerOutdated"] = True
            drifted.append(record)
            continue

        record["LocalDigest"] = next(iter(local_image.attrs.get("RepoDigests", [])), "").partition("@")[2]

        try:
            container = client.containers.get(container_name)
            record["ContainerOutdated"] = container.image.id != local_image.id
        except errors.NotFound:
            record["Running"] = False

        # An empty digest on either side means we could not read it, which is not the same
        # as knowing the two differ.
        if record["LocalDigest"] and record["RegistryDigest"]:
            record["ImageOutdated"] = record["LocalDigest"] != record["RegistryDigest"]

        if record["ContainerOutdated"] or record["ImageOutdated"] or not record["Running"]:
            drifted.append(record)

    logger.info("Image drift check found %d drifted service(s)", len(drifted))

    return drifted


def summarize(drifted: list[dict]) -> str:
    """Returns a one-line summary of the drift, or an empty string when everything matches"""

    if not drifted:
        return ""

    behind_registry = [record["Service"] for record in drifted if record["ImageOutdated"]]
    not_recreated = [record["Service"] for record in drifted if record["ContainerOutdated"]]
    not_running = [record["Service"] for record in drifted if not record["Running"]]

    parts = []

    if behind_registry:
        parts.append(f"{len(behind_registry)} behind registry ({' '.join(behind_registry)})")
    if not_recreated:
        parts.append(f"{len(not_recreated)} not recreated ({' '.join(not_recreated)})")
    if not_running:
        parts.append(f"{len(not_running)} not running ({' '.join(not_running)})")

    # No commas: set_status_for_ui strips them, since get_status_for_ui joins entries with one.
    return "Image drift: " + " | ".join(parts)
