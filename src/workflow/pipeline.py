"""Compatibility CLI and timing exports for the Rubrics sample workflow."""
import sys
from pathlib import Path

# Preserve direct script invocation as well as python -m src.workflow.pipeline.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.workflow.runtime import (
    TeeStream,
    tee_console_output,
    create_timing_wrapper,
    save_timing_log,
)


def main():
    """Compatibility CLI alias for the independent Rubrics sample route."""
    from src.workflow.exploration_cli import main as samples_main
    return samples_main()


if __name__ == "__main__":
    sys.exit(main())
