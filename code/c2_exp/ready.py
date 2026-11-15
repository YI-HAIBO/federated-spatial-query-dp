import urllib.request, sys, time
NODES = ["node1", "node2", "node3", "node4"]
for _ in range(60):
    ok = True
    for n in NODES:
        try:
            urllib.request.urlopen("http://%s:8000/" % n, timeout=2).read()
        except Exception:
            ok = False
    if ok:
        print("ALLREADY")
        sys.exit(0)
    time.sleep(1)
print("NOTREADY")
sys.exit(1)
