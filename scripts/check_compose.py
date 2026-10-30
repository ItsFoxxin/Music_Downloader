"""Check the expanded Compose topology without printing configuration secrets.

docker compose config --format json | python scripts/check_compose.py
"""
import json
import sys


def check(config):
    services = config["services"]
    expected = {"gateway", "web", "worker", "download-browser", "media", "gluetun", "qbittorrent"}
    assert expected <= services.keys(), "Missing bundled services"
    vpn, qbit, media = (services[name] for name in ("gluetun", "qbittorrent", "media"))
    assert not vpn.get("profiles") and not qbit.get("profiles"), "VPN must start by default"
    assert qbit["network_mode"] == "service:gluetun", "qBittorrent must share the VPN network"
    assert not qbit.get("ports") and not qbit.get("networks"), "Unexpected qBittorrent network exposure"
    assert qbit["depends_on"]["gluetun"]["condition"] == "service_healthy", "VPN health gate missing"
    port = int(qbit["environment"]["WEBUI_PORT"])
    assert vpn["environment"]["FIREWALL_INPUT_PORTS"] == str(port), "Web UI firewall mismatch"
    assert len(vpn["ports"]) == 1 and vpn["ports"][0]["target"] == port and int(vpn["ports"][0]["published"]) == port, "Unexpected VPN port exposure"
    for hook in ("VPN_PORT_FORWARDING_UP_COMMAND", "VPN_PORT_FORWARDING_DOWN_COMMAND"):
        assert f"http://127.0.0.1:{port}/api/" in vpn["environment"][hook], "Port-sync hook mismatch"
    qmounts = {v["target"]: v for v in qbit["volumes"]}
    mounts = {v["target"]: v for v in media["volumes"]}
    assert set(qmounts) == {"/config", "/downloads"}, "Unexpected qBittorrent mount"
    assert mounts["/staging"].get("read_only"), "Fox Den staging must be read-only"
    assert qmounts["/downloads"]["source"] == mounts["/staging"]["source"], "Staging sources differ"
    assert not qmounts["/downloads"].get("read_only"), "qBittorrent downloads must be writable"
    assert mounts["/media"]["source"] != mounts["/staging"]["source"], "Library and staging overlap"
    assert media["environment"]["MEDIA_BROWSER_HOME_URL"].startswith("https://"), "Media browser home must use HTTPS"
    assert "NET_ADMIN" in vpn["cap_add"], "VPN capability missing"
    assert all("NET_ADMIN" not in s.get("cap_add", []) for n, s in services.items() if n != "gluetun"), "VPN capability leaked"
    assert any(s["source"] == "proton_wireguard_private_key" for s in vpn["secrets"]), "VPN key secret missing"
    assert all(v.get("bind", {}).get("create_host_path", False) is False for v in qmounts.values()), "Mount paths must exist"


if __name__ == "__main__":
    check(json.load(sys.stdin))
    print("Bundled VPN/qBittorrent topology checks passed.")
