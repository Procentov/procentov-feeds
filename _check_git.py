import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
r = subprocess.run(["git", "log", "--oneline", "-4"], capture_output=True, text=True, cwd=r"C:\work\xml-feedy\procentov")
print(r.stdout)
print(r.stderr)
