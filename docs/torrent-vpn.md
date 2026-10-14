# Bundled qBittorrent and VPN

The main `compose.yaml` starts Gluetun and qBittorrent alongside Fox Den's five
application services. No extra Compose file or profile is needed:

```sh
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml logs --tail=100 gluetun qbittorrent media
```

`compose.vpn.yaml` remains an empty compatibility shim, so older two-file launch
commands still work without duplicating services.

## Configure before starting

Copy `.env.example` to `.env` and set the application settings described in the
main README, plus these VPN/client settings:

| Setting | Value |
| --- | --- |
| `WIREGUARD_PUBLIC_KEY` | Peer public key from your Proton WireGuard profile |
| `WIREGUARD_ENDPOINT_IP` / `WIREGUARD_ENDPOINT_PORT` | Profile's IPv4 endpoint and port |
| `WIREGUARD_ADDRESSES` | Interface address from that profile |
| `WIREGUARD_PRIVATE_KEY_FILE` | Host file containing only the private key |
| `GLUETUN_CONFIG_PATH` | Host Gluetun config directory |
| `TORRENT_CONFIG_PATH` | Host qBittorrent appdata directory |
| `TORRENT_STAGING_PATH` | Host download directory, mounted as `/downloads` in qBittorrent |
| `QBIT_URL` | Keep `http://gluetun:8080` for the bundled client |
| `QBIT_PUBLIC_URL` | Browser-reachable address, such as `http://your-server:8080` |
| `QBIT_BIND_IP` | Server LAN IP, or loopback when using a reverse proxy |
| `QBIT_WEB_PORT` | Web UI port on host and container; update both URLs when changing it |
| `QBIT_USERNAME` / `QBIT_PASSWORD` | Existing qBittorrent Web UI credentials |

Pre-create all bind directories and the key file; Compose intentionally refuses
to create missing bind paths. Keep the real `.env`, private key, and appdata out
of Git. The key is mounted only into Gluetun. This configuration uses the supplied
Proton custom WireGuard layout with IPv4 routing.

## First qBittorrent login

A fresh LinuxServer qBittorrent installation prints a temporary admin password in
its container logs. Sign into its Web UI, set a permanent password, then put that
same password in `.env` as `QBIT_PASSWORD`. Apply the app credential change:

```sh
docker compose -f compose.yaml up -d --force-recreate media
```

`QBIT_PASSWORD` lets Fox Den log in; it does not initialize or change qBittorrent's
own password. Keep qBittorrent CSRF and host-header protection enabled. Configure
its allowed hostname for `gluetun` and your public hostname if required. Use
`/downloads` for completed files and optionally `/downloads/incomplete` for
in-progress downloads. Keep `QBIT_DOWNLOAD_ROOT=/downloads`.

## Routing and port forwarding

qBittorrent shares Gluetun's network namespace and waits for its image health
check. It has no independent Docker network or published ports. Gluetun publishes
only the Web UI port and allows that same port through its input firewall. qBittorrent
mounts config and downloads; Fox Den mounts the same downloads read-only and
handles reviewed copies into the separate media library.

Only Gluetun receives `NET_ADMIN` and `/dev/net/tun`. LinuxServer qBittorrent and
the downloader browser have their own init/user models; the application's
non-root/read-only claims apply to Fox Den web, worker, and media services.

`VPN_PORT_FORWARDING=off` is the fresh-install default. Outbound torrent connections
can work without an incoming forwarded port. Enable forwarding only with a
compatible Proton profile/server and after configuring the supplied localhost
port-sync hooks. Those hooks require qBittorrent's localhost authentication bypass;
do not enable bypass for arbitrary LAN subnets. A failed hook means the forwarded
port was not synchronized. An existing `.env` value of `on` remains effective.

The original supplied files disagreed on IPv6 and the README's forwarding state.
Those were source discrepancies, not current NAS observations. Review the actual
VPN configuration before migrating.

## Migrate an existing torrent stack

1. Stop and back up the old stack, qBittorrent appdata, and WireGuard key.
2. Point the new bind variables at the explicitly verified host paths. Preserve
   the old `.env` and merge settings; do not overwrite it. Never run both stacks
   against the same appdata or listening port.
3. Set the internal URL and credentials, then start the main Compose stack.
4. Verify live tunnel health, qBittorrent network namespace/public egress, private
   Web UI authentication, and kill-switch behavior on the Linux Docker host.
5. Validate and import a small completed torrent; confirm the source still seeds.

After replacing Gluetun, recreate qBittorrent so it attaches to the current
network namespace:

```sh
docker compose -f compose.yaml up -d --force-recreate gluetun
docker compose -f compose.yaml up -d --force-recreate qbittorrent
```

No live VPN test or NAS migration was performed for this change. The application
can remain accessible when the VPN is unavailable, but torrent connectivity
requires a healthy tunnel.

References: [Gluetun container routing](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md),
[LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).
