"""Build-image smoke on GitHub's ephemeral Docker runner; no NAS mounts."""
import json
import subprocess
import time
import uuid


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, text=True, capture_output=True)


prefix = "foxden-ci-" + uuid.uuid4().hex[:12]
config = prefix + "-config"
staging = prefix + "-staging"
names = [prefix + "-web", prefix + "-worker"]
try:
    # Named volumes inherit the image's /config and /staging ownership.
    for name, command in zip(names, ["foxden-music-web", "foxden-music-worker"]):
        result = docker("run", "-d", "--name", name, "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777",
            "-v", config + ":/config", "-v", staging + ":/staging",
            "-e", "MUSIC_DIR=/tmp/music", "-e", "TMPDIR=/staging/.upload-tmp",
            "foxden-ci:local", command)
        print(f"Started {command}: {result.stdout.strip()[:12]}")
        kind = "web" if command.endswith("web") else "worker"
        for _ in range(60):
            state = json.loads(docker("inspect", name).stdout)[0]["State"]
            assert state["Running"], f"{command} exited: {docker('logs', name).stdout}"
            result = docker("exec", name, "python", "-m", "foxden_music.healthcheck", kind, check=False)
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"{command} health check failed: {result.stderr}")
        uid = docker("exec", name, "id", "-u").stdout.strip()
        assert uid != "0", "Service unexpectedly runs as root"
    probe = """import importlib.resources as r,urllib.request
from foxden_music import __version__
root=r.files('foxden_music')
for name in ['styles.css','workspace.css','app.js','browser.js','browser-home-bridge.js']:
    assert root.joinpath('static',name).is_file(), name
for route in ['/health','/','/add','/library','/static/workspace.css']:
    response=urllib.request.urlopen('http://127.0.0.1:8000'+route)
    assert response.status==200
print('Packaged UI and HTTP health passed',__version__)
"""
    print(docker("exec", names[0], "python", "-c", probe).stdout)
finally:
    for name in names:
        logs = docker("logs", "--tail", "40", name, check=False)
        print(logs.stdout, logs.stderr)
        docker("rm", "-f", name, check=False)
    for volume in [config, staging]:
        docker("volume", "rm", volume, check=False)
