import sys
import time
from collections.abc import Callable

from pydantic import ValidationError

from app.CLI_interface.inner_interface_functions import (
    FamilySelection,
    collect_custom_family_inputs,
    prompt_batch_size,
    select_family_members,
)
from app.CLI_interface.interface_formation import (
    select_generation_mode,
    select_random_generation_mode,
    show_generating,
    show_success,
    wait_for_keypress,
)
from app.batch_generation import (
    generate_batch_families,
)
from app.family_generation import generate_family
from app.history import HistoryError, load_recent_names, record_names
from app.person_generation import DuplicateGeneratedNameError
from app.pillow import DocumentGenerationError, generate_family_documents


def run_application(
    *,
    interactive: bool = False,
    input_fn: Callable[[], str] | None = None,
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] | None = None,
    pause_fn: Callable[[Callable[[], str]], None] | None = None,
) -> int:
    use_interactive_cli = interactive
    read_input = input if input_fn is None else input_fn
    sleep = time.sleep if sleep_fn is None else sleep_fn
    pause = (
        (lambda reader: wait_for_keypress(input_fn=reader))
        if pause_fn is None
        else pause_fn
    )

    while True:
        mode = (
            select_generation_mode(
                input_fn=read_input,
                output_fn=output_fn,
                sleep_fn=sleep,
            )
            if use_interactive_cli
            else "random"
        )
        if use_interactive_cli and mode == "random":
            random_mode = select_random_generation_mode(
                input_fn=read_input,
                output_fn=output_fn,
                sleep_fn=sleep,
            )
            if random_mode == "batch":
                batch_size = prompt_batch_size(
                    input_fn=read_input,
                    output_fn=output_fn,
                    sleep_fn=sleep,
                )
                show_generating(output_fn=output_fn)
                try:
                    result = generate_batch_families(
                        batch_size,
                        recent_names=load_recent_names(),
                    )
                except (
                    DocumentGenerationError,
                    HistoryError,
                    ValueError,
                ) as exc:
                    print(
                        f"Document generation failed: {_safe_failure_message(exc)}",
                        file=sys.stderr,
                    )
                    return 1
                show_success(
                    result.batch_directory.name,
                    custom=False,
                    output_fn=output_fn,
                )
                return 0

        selection = (
            select_family_members(
                input_fn=read_input,
                output_fn=output_fn,
                sleep_fn=sleep,
            )
            if use_interactive_cli
            else None
        )
        family_selection = selection if selection is not None else FamilySelection()
        custom_inputs = None
        if mode == "custom":
            custom_inputs = collect_custom_family_inputs(
                family_selection,
                input_fn=read_input,
                output_fn=output_fn,
                sleep_fn=sleep,
            )

        if use_interactive_cli:
            show_generating(output_fn=output_fn)
        try:
            recent_names = load_recent_names()
            family = generate_family(
                recent_names,
                family_selection,
                custom_inputs=custom_inputs,
            )
            documents = generate_family_documents(
                family.members,
                selection=family_selection,
                synthetic_parents=family.synthetic_parents,
            )
            record_names([member.name for member in family.members])
        except (
            DocumentGenerationError,
            HistoryError,
            ValueError,
        ) as exc:
            print(
                f"Document generation failed: {_safe_failure_message(exc)}",
                file=sys.stderr,
            )
            return 1

        if not use_interactive_cli:
            print("Document generation completed.")
            for index, (front_path, back_path) in enumerate(
                documents.member_image_paths, start=1
            ):
                print(f"Member {index} front image: {front_path}")
                print(f"Member {index} back image: {back_path}")
            for certificate_path in documents.certificate_paths:
                print(f"Certificate mockup: {certificate_path}")
            for document_path in documents.last_document_paths:
                print(f"Additional document: {document_path}")
            for front_path, back_path in documents.list_image_paths:
                print(f"List front image: {front_path}")
                print(f"List back image: {back_path}")
            return 0

        show_success(
            documents.family_directory.name,
            custom=mode == "custom",
            output_fn=output_fn,
        )
        if mode != "custom":
            return 0
        pause(read_input)


def _safe_failure_message(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "Generated document fields did not pass validation."
    if isinstance(error, DuplicateGeneratedNameError):
        return "Generated name conflicts with recent name history."
    return str(error)
