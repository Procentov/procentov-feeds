import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
cwd = r"C:\work\xml-feedy\procentov"

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    print(r.stdout.strip())
    if r.stderr.strip():
        print("STDERR:", r.stderr.strip())
    return r.returncode

run(["git", "add", "-A"])
rc = run(["git", "commit", "-m", "M1.3 finalizace: regex fix + slovnik rozsireni + description preklad"])
if rc == 0:
    push_rc = run(["git", "push", "origin", "main"])
    if push_rc != 0:
        print("[WARN] push selhal, lokalni commit OK")
else:
    print("[INFO] Nic k commitovani nebo chyba")
