"""
watcher.py — the Pi's ear for a wireless camera node.

A battery ESP32-S3 sits somewhere useful, sleeps at about 14 uA, wakes
when its PIR sees something, takes one frame, POSTs it here, and goes
back to sleep. This is the endpoint it POSTs to.

    POST /frame   body = raw JPEG
                  X-Kea-Token: <shared secret>
                  X-Kea-Name:  door            (optional, defaults "watcher")
    GET  /health  -> "ok", so the node can prove the Pi is up before it
                     bothers spending a radio second on an upload

WHY THE NODE PUSHES AND THE PI NEVER PULLS

The intuitive design is "Kea asks the camera for a picture". It is also
the design that kills the battery: to answer, the node has to be awake
and listening, which means no deep sleep, which means about four hours
instead of months. So the node owns the schedule and this end just
listens. The cost, stated plainly: Kea cannot take a picture on demand.
It can leave a flag (see pending_command) that the node picks up on its
NEXT wake, so "on demand" really means "within one event".

SECURITY, SUCH AS IT IS

A shared token in a header, compared with compare_digest. That is enough
to stop something else on your network posting junk into your dataset by
accident, and it is not enough to stop anyone who can already read your
traffic — it is plain HTTP on a LAN. Do not port-forward this. The token
is required: with none set the server refuses to start rather than
running wide open, because an image-upload endpoint with no auth is the
kind of thing you forget about.

Runs on a daemon thread with the stdlib http.server. No Flask, nothing
to install, consistent with the rest of the backend.
"""

import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("KEA_WATCHER_PORT", "842"))
TOKEN = os.getenv("KEA_WATCHER_TOKEN", "")
MAX_BYTES = int(os.getenv("KEA_WATCHER_MAX_KB", "512")) * 1024
COOLDOWN = float(os.getenv("KEA_WATCHER_COOLDOWN", "20"))


class Watcher:
    """Receives frames from remote nodes. Never blocks the render loop."""

    def __init__(self):
        self.enabled = bool(TOKEN)
        self.error = None if TOKEN else "KEA_WATCHER_TOKEN is not set"
        self._server = None
        self._thread = None
        self._lock = threading.Lock()
        self.nodes = {}          # name -> {last_seen, count, last_path, battery}
        self._recent = []        # newest first, capped
        self._commands = {}      # name -> str, collected on the node's next wake

    # ── server ─────────────────────────────────────────────────────────
    def start(self):
        """Idempotent. Returns True if listening."""
        if self._server is not None:
            return True
        if not self.enabled:
            return False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):        # noqa: A003 - quiet by default
                pass

            def _reply(self, code, body=b"", ctype="text/plain"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _authed(self):
                got = self.headers.get("X-Kea-Token", "")
                return hmac.compare_digest(got, TOKEN)

            def do_GET(self):                 # noqa: N802
                if self.path.startswith("/health"):
                    return self._reply(200, b"ok")
                return self._reply(404)

            def do_POST(self):                # noqa: N802
                if not self.path.startswith("/frame"):
                    return self._reply(404)
                if not self._authed():
                    return self._reply(401, b"bad token")
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return self._reply(400, b"bad length")
                if n <= 0 or n > MAX_BYTES:
                    # A node with a corrupt frame buffer will happily send
                    # megabytes; the Pi should not fill its card for it.
                    return self._reply(413, b"too big")
                data = self.rfile.read(n)
                name = (self.headers.get("X-Kea-Name") or "watcher")[:24]
                batt = self.headers.get("X-Kea-Battery")
                cmd = outer.accept(name, data, batt)
                return self._reply(200, json.dumps({"ok": True,
                                                    "command": cmd}).encode(),
                                   "application/json")

        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
        except OSError as exc:
            self.error = f"port {PORT}: {exc.strerror or exc}"
            return False
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:                                # noqa: BLE001
                pass
            self._server = None

    # ── receiving ──────────────────────────────────────────────────────
    def accept(self, name, jpeg, battery=None):
        """Store a frame and note the node. Returns a queued command or ""."""
        now = time.time()
        path = None
        try:
            from backend import dataset
            path = dataset.save_bytes(jpeg, tag=name,
                                      extra={"source": name,
                                             "battery": battery})
        except Exception:                                    # noqa: BLE001
            path = None

        with self._lock:
            node = self.nodes.setdefault(name, {"count": 0})
            node["last_seen"] = now
            node["count"] += 1
            node["last_path"] = path
            node["battery"] = battery
            self._recent.insert(0, {"name": name, "ts": now, "path": path})
            del self._recent[12:]
            cmd = self._commands.pop(name, "")

        self._maybe_alert(name, now)
        return cmd

    def _maybe_alert(self, name, now):
        """Tell Kea something moved — but not once per frame.

        A PIR staring at a doorway during a conversation will fire every
        few seconds. Alerting on each one would make the screen useless
        and train you to ignore it, so a node can only raise one alert per
        COOLDOWN.
        """
        node = self.nodes.get(name, {})
        if now - node.get("last_alert", 0) < COOLDOWN:
            return
        node["last_alert"] = now
        try:
            from backend.reminders import ReminderService
            ReminderService.instance().add_local(
                f"{name.upper()} saw something", ttl_s=COOLDOWN * 6)
        except Exception:                                    # noqa: BLE001
            pass

    # ── queries, for the UI ────────────────────────────────────────────
    def queue_command(self, name, cmd):
        """Left for the node to collect on its NEXT wake. This is what
        'on demand' honestly means for a sleeping device."""
        with self._lock:
            self._commands[name] = cmd

    def recent(self):
        with self._lock:
            return list(self._recent)

    def summary(self):
        """(online_count, [(name, seconds_since_seen, frames, battery)])."""
        now = time.time()
        with self._lock:
            rows = [(n, now - d.get("last_seen", 0), d.get("count", 0),
                     d.get("battery")) for n, d in sorted(self.nodes.items())]
        online = sum(1 for _n, age, _c, _b in rows if age < 3600)
        return online, rows


_singleton = None


def instance():
    global _singleton
    if _singleton is None:
        _singleton = Watcher()
    return _singleton
