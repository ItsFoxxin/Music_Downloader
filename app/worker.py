import json
import logging
import threading

from .files import audit, contained, import_files, target, validate

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings, store, qbit):
        self.s, self.store, self.qbit = settings, store, qbit
        self.stop = threading.Event()
        self.thread = None

    def recover(self):
        for job in self.store.jobs():
            if job["status"] != "interrupted" or job["kind"] != "import":
                continue
            try:
                p = job["payload"]
                destination = target(self.s, p["category"], p["name"])
                receipt = contained(self.s.media, destination.relative_to(self.s.media).as_posix() + "/.foxden-receipt.json")
                data = json.loads(receipt.read_text(encoding="utf-8"))
                if data["id"] == job["id"] and data["destination"] == destination.relative_to(self.s.media).as_posix():
                    self.store.record_import(job["id"], data["destination"], data)
                    checked = audit(self.s, self.store, job["id"])
                    self.store.finish(job["id"], {"destination": data["destination"], "recovered": True, "audit": checked})
            except (ValueError, OSError, KeyError):
                log.warning("Interrupted import %s needs manual review", job["id"])

    def run_one(self):
        job = self.store.claim()
        if not job:
            return False
        try:
            p = job["payload"]
            if job["kind"] == "validate":
                result = validate(self.s, self.qbit, p)
            elif job["kind"] == "import":
                result = import_files(self.s, self.store, self.qbit, p, job["id"])
            elif job["kind"] == "audit":
                result = audit(self.s, self.store, p["import_id"])
            elif job["kind"] == "torrent_action":
                self.qbit.action(p["torrent_hash"], p["action"])
                result = {"message": "Request accepted by qBittorrent. Check the torrent state for completion."}
            elif job["kind"] == "add":
                self.qbit.add(p["magnet"], p["category"])
                result = {"message": "Magnet link accepted by qBittorrent."}
            else:
                raise ValueError("Unknown job kind")
            self.store.finish(job["id"], result=result)
        except Exception as exc:
            log.warning("Job %s failed (%s)", job["id"], type(exc).__name__)
            self.store.finish(job["id"], error=str(exc)[:1500])
        return True

    def loop(self):
        self.recover()
        while not self.stop.is_set():
            if not self.run_one():
                self.stop.wait(0.5)

    def start(self):
        self.thread = threading.Thread(target=self.loop, daemon=True, name="media-worker")
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
