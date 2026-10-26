"""Run standalone tests without overwriting the player's settings or save."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_GL_TESTS = {'gl_pipeline_test.py', 'stage2_opengl_test.py'}
BOOT = '''
import os, sys, runpy, tempfile
if os.environ.get('NETHACK_REAL_VIDEO') != '1':
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
from engine import config as C
from game import lang
with tempfile.TemporaryDirectory() as tmp:
    C.SAVE_DIR = tmp
    C.SAVE_PATH = os.path.join(tmp, 'slot.json')
    lang.SETTINGS_PATH = os.path.join(tmp, 'settings.json')
    runpy.run_path(sys.argv[1], run_name='__main__')
'''

if __name__ == '__main__':
    names = sys.argv[1:] or sorted(n for n in os.listdir(os.path.dirname(__file__)) if n.endswith('_test.py'))
    failures = []
    for name in names:
        env = os.environ.copy()
        if name in REAL_GL_TESTS:
            env['NETHACK_REAL_VIDEO'] = '1'
        try:
            result = subprocess.run([sys.executable, '-u', '-c', BOOT, os.path.join('tests', name)],
                                    cwd=ROOT, capture_output=True, text=True, env=env,
                                    timeout=600 if name in ('stress_test.py','smoke_test.py','items_test.py') else 90)
            print(name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
            if result.returncode:
                failures.append(name)
                print(result.stdout, result.stderr, flush=True)
            elif name == 'perf_test.py':
                print(result.stdout, flush=True)
        except subprocess.TimeoutExpired:
            failures.append(name)
            print(name, 'TIMEOUT', flush=True)
    print('Failed:', failures, flush=True)
    sys.exit(bool(failures))
