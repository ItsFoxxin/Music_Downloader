"""Check release metadata, deployment parity, and accidental private artifacts."""
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
project = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())
version = project["project"]["version"]
init = (ROOT / "backend/src/foxden_music/__init__.py").read_text()
assert f'__version__ = "{version}"' in init
requirements = (ROOT / "backend/requirements.txt").read_text().splitlines()
assert set(project["project"]["dependencies"]) == {line for line in requirements if line and not line.startswith("#")}
compose = (ROOT / "docker-compose.yaml").read_bytes()
assert compose == (ROOT / "docker-compose.yml").read_bytes(), "Compose variants differ"
assert f"image: fox-den-music:{version}" in compose.decode()
assert "context: ./backend" in compose.decode()
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
for name in filter(None, tracked):
    parts = Path(name).parts
    assert not any(p in {"data", "secrets", "__pycache__", ".venv"} for p in parts), name
    assert not (Path(name).name.startswith(".env") and Path(name).name != ".env.example"), name
    assert not re.search(r"\.(env|db|sqlite3?|pyc|zip|mp3|flac|m4a)$", name), name
for sample in (".env", ".env.prod", "secrets/key.txt", "data/jobs.db", "downloads/album.zip"):
    subprocess.run(["git", "check-ignore", "-q", sample], cwd=ROOT, check=True)
print(f"v{version}: dependency pins, Compose parity and source-only tracking passed")
