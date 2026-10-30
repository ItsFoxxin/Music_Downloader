# Private deployment secrets

Keep the real Proton WireGuard private key outside Git. For the bundled VPN
container, create `proton-wireguard-private-key.txt` here or configure an external
absolute `WIREGUARD_PRIVATE_KEY_FILE` in `.env`. The file contains only the key.

No private key, recovery password, qBittorrent appdata, or populated `.env` from the
supplied torrent stack is included in this repository.
