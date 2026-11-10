from collections.abc import Callable

from app.CLI_interface.errors import InputRetryLimitError
from app.orchestration import run_application


def main(
    *,
    interactive: bool = False,
    input_fn: Callable[[], str] | None = None,
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] | None = None,
    pause_fn: Callable[[Callable[[], str]], None] | None = None,
) -> int:
    """Run the CLI/application workflow and return its process exit status."""
    try:
        return run_application(
            interactive=interactive,
            input_fn=input_fn,
            output_fn=output_fn,
            sleep_fn=sleep_fn,
            pause_fn=pause_fn,
        )
    except InputRetryLimitError as exc:
        import sys

        print(str(exc), file=sys.stderr)
        return 1
