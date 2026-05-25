import subprocess, os, sys, time

BASE = r'C:\Users\redem\RedDirt-Tunes'
os.makedirs(os.path.join(BASE, '.reddirt', 'output'), exist_ok=True)

def start(rel_cmd, rel_log):
    cmd = [sys.executable, os.path.join(BASE, rel_cmd)]
    log = os.path.join(BASE, rel_log)
    with open(log, 'w') as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT,
            cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
    return p

model = start('training/model_server.py', '.reddirt/output/model.log')
time.sleep(2)
voc = start('training/vocoder_server.py', '.reddirt/output/vocoder.log')
time.sleep(2)
print(f"[starter] Model PID: {model.pid}, Vocoder PID: {voc.pid}")
