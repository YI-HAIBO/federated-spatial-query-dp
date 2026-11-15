import subprocess, sys, os, time, threading, http.server, socketserver, json

DIR = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs\c2_exp"
# start a dummy node server on 8000 locally
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = b'{"ok":1}'
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 8000), H)
t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
time.sleep(0.5)

# run measure.py but it targets node1..node4 hostnames -> need /etc/hosts or localhost alias.
# Patch: run measure.py with a local stub that resolves node1..node4 to 127.0.0.1 via monkeypatch is complex.
# Instead, test the write logic in isolation: import measure, override NODES
sys.path.insert(0, DIR)
import importlib.util
spec = importlib.util.spec_from_file_location("measure", os.path.join(DIR, "measure.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.NODES = ["127.0.0.1"]  # single target
m.N = 10
m.PORT = 8000
out = os.path.join(DIR, "local_test.csv")
import io
# monkeypatch sys.argv and call main
import builtins
sys.argv = ["measure.py", "--mode", "localtest", "--out", out]
try:
    m.main()
    print("MAIN_OK")
except Exception as e:
    print("MAIN_ERR", repr(e))
# read back
if os.path.exists(out):
    with open(out) as f:
        print("CSV_CONTENT:\n" + f.read())
else:
    print("CSV_MISSING")
srv.shutdown()
