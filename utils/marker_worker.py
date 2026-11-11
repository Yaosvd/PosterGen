"""Local extraction only; process exit releases all CUDA allocations."""
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from utils.concurrency import slot, settings
from utils.persistence import _atomic_json


def main():
    pdf, name, content, assets, receipt = sys.argv[1:]
    # Do not release a model slot while CUDA objects/tracebacks are still alive.
    with slot('marker') as queued:
        code = 1
        try:
            signal.alarm(settings().get('marker_timeout_seconds', 1800))
            visible = os.environ['CUDA_VISIBLE_DEVICES']
            started = time.monotonic()
            from src.agents.parser import Parser
            from marker.settings import settings as marker_settings
            from surya.settings import settings as surya_settings
            os.environ['CUDA_VISIBLE_DEVICES'] = visible
            # With one visible UUID, cuda means logical device zero. Preserve
            # Marker's exact 'cuda' dtype branch (cuda:0 selects float32 there).
            marker_settings.TORCH_DEVICE = surya_settings.TORCH_DEVICE = 'cuda'
            parser = Parser()
            raw, rendered = parser._extract_raw_text(pdf, Path(content))
            figures, tables = parser._extract_assets(rendered, name, Path(assets))
            parser._cleanup_unused_assets(Path(assets), name, figures, tables)
            _atomic_json(Path(receipt), {'raw_text': raw, 'figures': figures, 'tables': tables,
                'queue_seconds': queued, 'extraction_seconds': time.monotonic()-started})
            code = 0
        except BaseException:
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)


if __name__ == '__main__':
    main()
