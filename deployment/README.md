# v3-deployment repo

WIP

## What's this?
Source of truth for manifest files for Orbs v3 validator nodes.

## how is it used
`v3-node-setup` clones this repo to the target node
`v3-manager` is responsible to keep it up to date upon new releases

## files
- `docker-compose.yml` - descriptor of the nodes service topoly and image versions.
- `nginx.conf` - config for single port 80 listener.
- `public.env` - variables which re not node specific

## todo
- expose public files of this folder via nginx