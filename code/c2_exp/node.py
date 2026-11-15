import http.server, socketserver, json, time, sys, random

QMS = 2.0  # 模拟空间查询单节点计算耗时(ms)

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path == "/":
            body = json.dumps({"ok": 1, "t": time.time()}).encode()
        elif self.path.startswith("/query"):
            qms = QMS
            for part in self.path.split("&"):
                if part.startswith("qms="):
                    try:
                        qms = float(part.split("=")[1])
                    except Exception:
                        pass
            time.sleep(qms / 1000.0)
            body = json.dumps({"result": int(qms * 10), "t": time.time()}).encode()
        else:
            body = b'{"ok":0}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    port = 8000
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), H) as httpd:
        print("NODE_READY port=%d" % port, flush=True)
        httpd.serve_forever()
