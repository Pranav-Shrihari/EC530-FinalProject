import subprocess, sys
from pkg_resources import resource_filename

def main():
    # Locate your packaged app.py
    script = resource_filename(__name__, 'app.py')
    # Delegate to streamlit
    subprocess.run(
        [sys.executable, '-m', 'streamlit', 'run', script] + sys.argv[1:],
        check=True
    )
