"""The stand the projector talks to, inside the container: /res/<path> is
served the way the launcher's LocalServer serves the game (the first root
that has the file wins: the run's own files, then the client's res), and
what the film POSTs to /res/report is kept for check.py. Every request is
written to requests.log. 127.0.0.1 only; the container has no network.

    python3 stand.py PORT ROOT[,ROOT...] OUTDIR
"""
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
ROOTS = [os.path.realpath(r) for r in sys.argv[2].split(",")]
OUT = sys.argv[3]
os.makedirs(OUT, exist_ok=True)
TYPES = {".swf": "application/x-shockwave-flash", ".xml": "text/xml", ".jpg": "image/jpeg", ".png": "image/png"}
REQ = open(os.path.join(OUT, "requests.log"), "a", buffering=1, encoding="utf-8")
N = [0]


class Stand(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        rel = path[len("/res/"):] if path.startswith("/res/") else None
        for root in (ROOTS if rel else ()):
            full = os.path.realpath(os.path.join(root, rel))
            if full.startswith(root + os.sep) and os.path.isfile(full):
                with open(full, "rb") as fh:
                    data = fh.read()
                REQ.write("GET %s 200 %d from %s\n" % (path, len(data), root))
                self.send_response(200)
                self.send_header("Content-Type", TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        REQ.write("GET %s 404\n" % path)
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("latin-1")
        q = urllib.parse.parse_qs(body, keep_blank_values=True)
        name = (q.get("name") or ["?"])[0]
        text = (q.get("body") or [""])[0]
        N[0] += 1
        if name == "log":
            with open(os.path.join(OUT, "log.txt"), "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
            with open(os.path.join(OUT, "%03d_%s.txt" % (N[0], safe)), "w", encoding="utf-8") as fh:
                fh.write(text)
        REQ.write("POST %s %s %d bytes\n" % (self.path, name, len(body)))
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


ThreadingHTTPServer(("127.0.0.1", PORT), Stand).serve_forever()
