"""Distinguish pinned VSR's empty OCR result from inference failures.

An empty detection is allowed for PRIVATE drafts only, never certified as
removed text. All other failures, timeouts and absent outputs remain errors.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile


def clean_or_detect_empty(python, backend, source, output, *, timeout=4800):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('VSR input and output must differ')
    output.unlink(missing_ok=True)
    command = [str(python), str(backend), '-i', str(source), '-o', str(output),
               '--inpaint-mode', 'sttn-det']
    with tempfile.TemporaryFile(mode='w+b') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
        log.seek(0, 2)
        log.seek(max(0, log.tell() - 32768))
        tail = log.read().decode('utf-8', errors='replace').strip()
    tail = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', tail)
    if result.returncode:
        # Match the precise terminal exception AND its pinned upstream raise.
        # Merely mentioning "No subtitles detected" in a log is insufficient.
        expected = 'Exception: No subtitles detected. Check file: ' + str(source)
        detection_raise = "raise Exception(tr['Main']['NoSubtitleDetected'].format(self.video_path))"
        exceptions = [line.strip() for line in tail.splitlines()
                      if re.match(r'^(?:[\w.]+(?:Error|Exception)|Exception):', line.strip())]
        if exceptions == [expected] and detection_raise in tail:
            output.unlink(missing_ok=True)
            shutil.copyfile(source, output)
            return {'text_removal_applied': False,
                    'text_detection_status': 'no_text_detected',
                    'human_quality_review_required': True}
        output.unlink(missing_ok=True)
        # Keep inference diagnostics useful without disclosing inherited secrets.
        safe_tail = tail[-6000:]
        for name, value in os.environ.items():
            if value and re.search(r'KEY|TOKEN|PASSWORD|SECRET|ENDPOINT', name):
                safe_tail = safe_tail.replace(value, '[redacted]')
        print(safe_tail, flush=True)
        raise RuntimeError('VSR inference failed; private draft blocked (no fallback)')
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError('VSR returned no readable output; private draft blocked')
    return {'text_removal_applied': True,
            'text_detection_status': 'text_inpainted',
            'human_quality_review_required': True}
