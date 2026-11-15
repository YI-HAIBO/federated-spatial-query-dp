import paramiko, io, os, time, sys, base64, hashlib

HOST, USER, PASS = "192.168.235.128", "cloud", "123456"
REMOTE = "/home/cloud/c2exp"
LOCAL = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs\c2_exp"
OUTLOC = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs"

FILES = ["node.py", "measure.py", "ready.py", "Dockerfile", "docker-compose.yml"]
log = []
def L(s):
    log.append(str(s)); print(s)

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
sftp = cli.open_sftp()

def run(cmd, timeout=300):
    _, o, e = cli.exec_command(cmd, timeout=timeout)
    try:
        out = o.read().decode("utf-8","replace")
    except Exception:
        out = "<tout>"
    try:
        err = e.read().decode("utf-8","replace")
    except Exception:
        err = "<terr>"
    return out, err

def sudo_run(cmd, timeout=120):
    stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -c " + shquote(cmd), timeout=timeout)
    stdin.write("123456\n"); stdin.flush()
    try:
        out = stdout.read().decode("utf-8","replace")
    except Exception:
        out = "<tout>"
    try:
        err = stderr.read().decode("utf-8","replace")
    except Exception:
        err = "<terr>"
    return out, err

def shquote(s):
    return "'" + s.replace("'", "'\\''") + "'"

def upload(f):
    lp = os.path.join(LOCAL, f)
    with open(lp, "rb") as fh:
        data = fh.read()
    b64 = base64.b64encode(data).decode()
    local_md5 = hashlib.md5(data).hexdigest()
    run("echo '%s' | base64 -d > %s/%s" % (b64, REMOTE, f))
    o, _ = run("md5sum %s/%s" % (REMOTE, f))
    remote_md5 = o.strip().split()[0] if o.strip() else ""
    ok = (remote_md5 == local_md5)
    L("UPLOAD %s md5=%s ok=%s" % (f, local_md5[:10], ok))
    return ok

# 1. mkdir + upload all (base64 + md5 verify)
run("mkdir -p %s" % REMOTE)
for f in FILES:
    if not upload(f):
        L("UPLOAD FAIL " + f); sys.exit(1)

# 2. build
L("== BUILD ==")
out, err = run("cd %s && docker build -t c2node:latest . 2>&1" % REMOTE, timeout=900)
L(out[-1200:])

# 3. compose up
L("== COMPOSE UP ==")
out, err = run("cd %s && docker compose up -d --no-build 2>&1" % REMOTE, timeout=300)
L(out[-900:])

# 4. wait
L("== WAIT ==")
out, err = run("docker exec c2client python3 /app/ready.py", timeout=180)
L("READY: " + out.strip()[-80:])

# 5. baseline
L("== BASELINE ==")
o, e = run("docker exec c2client python3 /app/measure.py --mode baseline --out /app/baseline.csv", timeout=500)
L("BASELINE_STDOUT: " + o[-200:] + " STDERR: " + e[-300:])
o, e = run("docker exec c2client cat /app/baseline.csv")
L("BASELINE_CSV(%d):\n%s" % (len(o), o))

# 6. delays
def inject(delay_ms):
    for c in ["c2node1","c2node2","c2node3","c2node4"]:
        out, _ = run("docker inspect -f '{{.State.Pid}}' %s" % c)
        pid = out.strip()
        if not pid.isdigit():
            L("PID FAIL " + c + " " + repr(out)); continue
        sudo_run("nsenter -t %s -n tc qdisc replace dev eth0 root netem delay %dms" % (pid, delay_ms))
    out, _ = run("docker inspect -f '{{.State.Pid}}' c2node1")
    pid = out.strip()
    out, _ = sudo_run("nsenter -t %s -n tc qdisc show dev eth0" % pid)
    L("TC pid=%s -> %s" % (pid, out.strip()[:150]))

for d in [10, 30, 80]:
    L("== DELAY %dms ==" % d)
    inject(d)
    o, e = run("docker exec c2client python3 /app/measure.py --mode delay%d --out /app/delay%d.csv" % (d, d), timeout=500)
    L("DELAY%d_STDOUT: %s STDERR: %s" % (d, o[-150:], e[-300:]))
    o, e = run("docker exec c2client cat /app/delay%d.csv" % d)
    L("DELAY%d_CSV(%d):\n%s" % (d, len(o), o))

# 7. collect via exec cat -> local write
os.makedirs(OUTLOC, exist_ok=True)
for f in ["baseline.csv","delay10.csv","delay30.csv","delay80.csv"]:
    out, _ = run("docker exec c2client cat /app/%s" % f)
    with io.open(os.path.join(OUTLOC, "C2_" + f), "w", encoding="utf-8") as fh:
        fh.write(out)
    L("SAVED C2_" + f + " (%d bytes)" % len(out))

# 8. cleanup (keep image for potential rerun; remove containers+network)
L("== CLEANUP ==")
out, err = run("cd %s && docker compose down 2>&1 | tail -3" % REMOTE, timeout=300)
L(out[-400:])

cli.close()
with io.open(os.path.join(OUTLOC, "_c2_vm_run.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(log))
print("DRIVER_DONE")
