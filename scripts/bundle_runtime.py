"""Bundle a relocatable uv-managed Python for real project commands."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=Path('dist/runtime/python'))
    args=parser.parse_args()
    subprocess.run(['uv','python','install','3.12'],check=True)
    python=Path(subprocess.check_output(['uv','python','find','--managed-python','--no-project','3.12'],text=True).strip())
    source=python.parent.parent if python.parent.name=='bin' else python.parent
    destination=args.destination.resolve()
    if destination.exists():raise SystemExit('Runtime destination already exists. Use a clean build folder.')
    shutil.copytree(source,destination,symlinks=True)
    # Preserve venv-independent, relocatable links. Reject links outside the bundle.
    for path in destination.rglob('*'):
        if path.is_symlink():
            value=os.readlink(path)
            if os.path.isabs(value):
                relative=Path(value).relative_to(source)
                path.unlink();path.symlink_to(os.path.relpath(destination/relative,path.parent))
    executable=destination/python.relative_to(source)
    subprocess.run([str(executable),'-I','-c','import ssl, sqlite3, venv, tkinter; print("Bundled project runtime ready")'],check=True)


if __name__=='__main__':main()
