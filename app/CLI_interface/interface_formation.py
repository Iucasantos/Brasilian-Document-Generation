import os
import sys
from collections.abc import Callable

from app.CLI_interface.errors import (
    InputRetryLimitError,
    MAX_INVALID_INPUT_ATTEMPTS,
)

_BORDER = "=" * 43


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def display_page(
    message: str,
    *,
    output_fn: Callable[..., None] = print,
) -> None:
    clear_screen()
    output_fn(_BORDER)
    output_fn(message)
    output_fn(_BORDER)


def prompt_page(
    message: str,
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
) -> str:
    clear_screen()
    output_fn(_BORDER)
    output_fn(message)
    output_fn(_BORDER)
    output_fn(">> ", end="", flush=True)
    return input_fn()


def select_generation_mode(
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None],
) -> str:
    for _ in range(MAX_INVALID_INPUT_ATTEMPTS):
        clear_screen()
        output_fn(_BORDER)
        output_fn("1 - Geração Randomizada")
        output_fn("2 - Geração Customizada")
        output_fn(_BORDER)
        output_fn(">> ", end="", flush=True)
        choice = input_fn().strip()
        if choice == "1":
            return "random"
        if choice == "2":
            return "custom"
        display_page("Invalid data!", output_fn=output_fn)
        sleep_fn(3)
    display_page("Too many invalid attempts. Returning to menu.", output_fn=output_fn)
    raise InputRetryLimitError("Generation mode remained invalid after repeated attempts.")


def select_random_generation_mode(
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None],
) -> str:
    for _ in range(MAX_INVALID_INPUT_ATTEMPTS):
        clear_screen()
        output_fn(_BORDER)
        output_fn("1 - Geração única")
        output_fn("2 - Geração em batch")
        output_fn(_BORDER)
        output_fn(">> ", end="", flush=True)
        choice = input_fn().strip()
        if choice == "1":
            return "single"
        if choice == "2":
            return "batch"
        display_page("Invalid data!", output_fn=output_fn)
        sleep_fn(3)
    display_page("Too many invalid attempts. Returning to menu.", output_fn=output_fn)
    raise InputRetryLimitError(
        "Random generation mode remained invalid after repeated attempts."
    )


def show_generating(*, output_fn: Callable[..., None] = print) -> None:
    display_page("Generating...", output_fn=output_fn)


def show_success(
    folder_name: str,
    *,
    custom: bool,
    output_fn: Callable[..., None] = print,
) -> None:
    display_page(
        f"Document {folder_name} generated successfully on output folder!",
        output_fn=output_fn,
    )
    if custom:
        output_fn("Press any key to continue.")


def wait_for_keypress(*, input_fn: Callable[[], str]) -> None:
    if os.name == "nt" and sys.stdin.isatty():
        import msvcrt

        msvcrt.getch()
        return
    input_fn()
