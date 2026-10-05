# qBittorrent and VPN integration

## Connect an existing stack (default)

Set `QBIT_URL` to the existing Web UI address reachable from Docker, and
`QBIT_PUBLIC_URL` to the address your browser uses. Set credentials in your private
`.env`. Set `TORRENT_STAGING_PATH` to the host download directory, and
`QBIT_DOWNLOAD_ROOT` to qBittorrent's corresponding container path (usually `/downloads`).

Fox Den mounts that host directory read-only and connects to qBittorrent through
its API. It does not need the VPN private key, access to the Docker socket, or
changes to qBittorrent's network namespace. Keep CSRF and host-header protections
enabled in qBittorrent; configure the actual expected hostname when necessary.

## Optional single-project stack

`compose.vpn.yaml` adds Gluetun and qBittorrent to the same Docker project. Fill
the VPN variables in `.env`, place your private key at `WIREGUARD_PRIVATE_KEY_FILE`,
set `QBIT_URL=http://gluetun:8080`, and use the externally reachable address for
`QBIT_PUBLIC_URL`. qBittorrent shares Gluetun's network namespace and has no own
ports or independent Docker network. Only the staging folder is mounted into it.

```sh
docker compose -f compose.yaml -f compose.vpn.yaml config --quiet
docker compose -f compose.yaml -f compose.vpn.yaml up -d --build
```

Before migrating a live torrent stack, stop and back up the old stack, preserve its
qBittorrent appdata and WireGuard key, and point the new bind variables at those
same explicitly verified paths. Do not run old and new stacks against the same
appdata or listening port simultaneously. There is no automatic migration script.

The optional VPN extension follows the supplied Gluetun/Proton layout with IPv4
only. The supplied `compose.yaml` and `docker-compose.yaml` differed on IPv6, and
the old README described port forwarding as disabled while both Compose files
enabled it. Those are unresolved source discrepancies, not current NAS observations.
The extension makes port forwarding configurable and does not change the original
deployment. Review your actual VPN configuration before adopting it.

The supplied port-forwarding hooks update qBittorrent through localhost. If you
retain these hooks, the qBittorrent localhost-auth-bypass setting must match that
configuration. Do not enable bypass for arbitrary LAN subnets. A failed hook means
the forwarded port was not synchronized; it does not mean Fox Den validated the VPN.

The Gluetun image necessarily requires `NET_ADMIN` and `/dev/net/tun`. These are
granted only to Gluetun. LinuxServer qBittorrent and the inherited Firefox image
have their own init/user models; the app's non-root/read-only claims apply to the
Fox Den web, worker, and media services, not to these third-party init processes.

After deployment, verify live tunnel health, torrent network namespace, public
egress, private Web UI authentication, and kill-switch behavior. Restart qBittorrent
after replacing Gluetun so it attaches to the current namespace. No live VPN test
or NAS migration was performed in this development build.

References: [qBittorrent API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29),
[Gluetun container routing](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md),
[LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).
