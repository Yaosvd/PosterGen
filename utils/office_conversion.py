"""Isolated LibreOffice supervisor; holds its slot even if its caller dies."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from utils.concurrency import slot, inherited_lease


def convert(pptx, output_dir, fmt, timeout=120, executable=None):
    import shutil
    executable = executable or shutil.which('libreoffice') or shutil.which('soffice')
    if not executable:
        raise FileNotFoundError('LibreOffice is not installed')
    command = [sys.executable, '-m', 'utils.office_conversion', executable,
               str(Path(pptx).resolve()), str(Path(output_dir).resolve()), fmt, str(timeout)]
    # The supervisor owns timeout, temporary profile and resource slot. It remains
    # alive to reap LibreOffice if the generation worker unexpectedly disappears.
    result = subprocess.run(command, capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1], pass_fds=inherited_lease())
    if result.returncode:
        raise RuntimeError(f'LibreOffice conversion failed: {result.stderr[-4000:]}')
    target = Path(output_dir) / (Path(pptx).stem + '.' + fmt.split(':')[0])
    if not target.is_file() or not target.stat().st_size:
        raise RuntimeError('LibreOffice did not produce the requested artifact')
    return target


def main():
    executable, pptx, output, fmt, seconds = sys.argv[1:]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with slot('render'), tempfile.TemporaryDirectory(prefix='rubrics-office-') as temp:
        root = Path(temp)
        command = [executable, f'-env:UserInstallation={(root / "profile").as_uri()}',
                   '--headless', '--convert-to', fmt, '--outdir', str(root), pptx]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=float(seconds))
            if process.returncode:
                raise RuntimeError(f'LibreOffice exit {process.returncode}: {stderr}')
            artifact = root / (Path(pptx).stem + '.' + fmt.split(':')[0])
            if not artifact.is_file() or not artifact.stat().st_size:
                raise RuntimeError(f'LibreOffice produced no artifact: {stdout} {stderr}')
            # Never accept a stale artifact left in the caller's output directory.
            import shutil
            fd, name = tempfile.mkstemp(prefix='.office-', dir=output)
            os.close(fd)
            try:
                shutil.copyfile(artifact, name)
                os.replace(name, output / artifact.name)
            finally:
                Path(name).unlink(missing_ok=True)
        finally:
            # Also reap descendants if the launcher exited before soffice.bin.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()


if __name__ == '__main__':
    main()
