import os
import random
import shutil
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.CLI_interface.inner_interface_functions import FamilySelection
from app.schema import CINSchema, _add_years, _age_on

from .document_editor import (
    DEFAULT_COORDINATES_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PORTRAIT_DIR,
    DEFAULT_TEMPLATES_DIR,
    DocumentGenerationError,
    _folder_name,
    create_document_images,
    create_list_document_images,
    select_cin_portrait,
)
from .special_documents import render_family_certificates, render_last_documents


@dataclass(frozen=True)
class FamilyDocumentResult:
    family_directory: Path
    member_image_paths: tuple[tuple[Path, Path], ...]
    certificate_paths: tuple[Path, ...] = ()
    list_image_paths: tuple[tuple[Path, Path], ...] = ()
    last_document_paths: tuple[Path, ...] = ()


def _list_field_values(
    person: CINSchema,
    *,
    today: date,
    rng: random.Random,
) -> tuple[dict[str, object], dict[str, object]]:
    twentieth_birthday = _add_years(person.date_of_birth, 20)
    if twentieth_birthday > today:
        raise ValueError("List generation requires the person to be at least 20.")

    first_hab_date = date.fromordinal(
        rng.randint(twentieth_birthday.toordinal(), today.toordinal())
    )
    earliest_c_val = _add_years(first_hab_date, 10)
    latest_c_val = _add_years(today, 10)
    c_val = date.fromordinal(
        rng.randint(earliest_c_val.toordinal(), latest_c_val.toordinal())
    )

    candidate_issue_date = date.fromordinal(
        rng.randint(twentieth_birthday.toordinal(), today.toordinal())
    )
    interval_years = max(0, _age_on(first_hab_date, candidate_issue_date) // 10 * 10)
    issue_date = _add_years(first_hab_date, interval_years)
    uf = person.naturality.rsplit("/", 1)[-1]

    front_fields: dict[str, object] = {
        "nome": person.name,
        "gg": f"{rng.randrange(10**7):07d}",
        "card_issuer": person.card_issuer,
        "uf": uf,
        "cpf": person.cpf,
        "date_of_birth": person.date_of_birth,
        "filiation": person.filliation,
        "hab": "B",
        "first_hab_date": first_hab_date,
        "c_val": c_val,
        "c_num_reg": f"{rng.randrange(10**11):011d}",
    }
    back_fields: dict[str, object] = {
        "arr": person.name,
        "place_of_issue": person.place_of_issue,
        "issue_date": issue_date,
    }
    return front_fields, back_fields


def generate_document(
    person: CINSchema,
    *,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    portrait_dir: Path = DEFAULT_PORTRAIT_DIR,
    coordinates_path: Path = DEFAULT_COORDINATES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    portrait_path: Path | None = None,
) -> tuple[Path, Path]:
    """Generate CIN images, optionally reusing a selected source portrait file."""
    # Font, text color, and fitted font-size limits are configured in document_editor.py.
    return create_document_images(
        person,
        templates_dir=templates_dir,
        portrait_dir=portrait_dir,
        coordinates_path=coordinates_path,
        output_dir=output_dir,
        portrait_path=portrait_path,
    )


def generate_family_documents(
    members: Sequence[CINSchema],
    *,
    selection: FamilySelection | None = None,
    synthetic_parents: Sequence[CINSchema] = (),
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    portrait_dir: Path = DEFAULT_PORTRAIT_DIR,
    coordinates_path: Path = DEFAULT_COORDINATES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    certificate_rng: random.Random | None = None,
    list_rng: random.Random | None = None,
    last_document_rng: random.Random | None = None,
    today: date | None = None,
) -> FamilyDocumentResult:
    if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
        raise TypeError("members must be a sequence of CINSchema instances.")
    if not members:
        raise ValueError("A family must contain its titular.")
    if any(not isinstance(member, CINSchema) for member in members):
        raise TypeError("Every family member must be a validated CINSchema instance.")
    if not isinstance(synthetic_parents, Sequence) or isinstance(
        synthetic_parents, (str, bytes)
    ):
        raise TypeError("synthetic_parents must be a sequence of CINSchema instances.")
    if any(not isinstance(parent, CINSchema) for parent in synthetic_parents):
        raise TypeError("Every synthetic parent must be a validated CINSchema instance.")
    if selection is not None and not isinstance(selection, FamilySelection):
        raise TypeError("selection must be a FamilySelection.")
    if selection is None and synthetic_parents:
        raise ValueError(
            "A family selection is required when synthetic parent data is provided."
        )

    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to create output directory '{output_dir}': {exc}"
        ) from exc

    titular = members[0]
    family_id = uuid.uuid4().hex
    age = _age_on(titular.date_of_birth, date.today())
    parents = selection.parents if selection is not None else 0
    spouse = int(selection.spouse) if selection is not None else 0
    children = selection.children if selection is not None else 0
    family_directory = output_dir / (
        f"M={len(members) - 1}_{_folder_name(titular.name)}_{age}_"
        f"P={parents}_C={spouse}_F={children}_{family_id}"
    )
    if family_directory.exists():
        raise DocumentGenerationError(
            f"Family output directory already exists: '{family_directory}'."
        )
    try:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=f".{family_id}_family_", dir=output_dir)
        )
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to create a family staging directory under '{output_dir}': {exc}"
        ) from exc

    staged_paths: list[tuple[Path, Path]] = []
    member_identifiers: list[str] = []
    staged_certificate_paths: tuple[Path, ...] = ()
    staged_last_document_paths: tuple[Path, ...] = ()
    staged_list_paths: list[tuple[Path, Path]] = []
    generation_date = today or date.today()
    list_random = random.Random() if list_rng is None else list_rng
    try:
        for index, person in enumerate(members):
            identifier = family_id if index == 0 else uuid.uuid4().hex
            member_identifiers.append(identifier)
            portrait_path = select_cin_portrait(person, portrait_dir=portrait_dir)
            staged_paths.append(
                create_document_images(
                    person,
                    templates_dir=templates_dir,
                    portrait_dir=portrait_dir,
                    coordinates_path=coordinates_path,
                    output_dir=staging_directory / "CIN",
                    identifier=identifier,
                    portrait_path=portrait_path,
                )
            )
            member_age = _age_on(person.date_of_birth, generation_date)
            if member_age > 21:
                front_fields, back_fields = _list_field_values(
                    person,
                    today=generation_date,
                    rng=list_random,
                )
                list_directory = (
                    staging_directory
                    / "CNH"
                    / f"{_folder_name(person.name)}_{member_age}_{identifier}"
                )
                staged_list_paths.append(
                    create_list_document_images(
                        front_fields,
                        back_fields,
                        portrait_path,
                        templates_dir=templates_dir,
                        coordinates_dir=Path(coordinates_path).parent,
                        output_dir=list_directory,
                    )
                )
        if selection is not None:
            staged_certificate_paths = render_family_certificates(
                members,
                selection,
                synthetic_parents,
                member_identifiers,
                templates_dir=Path(templates_dir),
                coordinates_dir=Path(coordinates_path).parent,
                output_dir=staging_directory / "Cert",
                rng=certificate_rng or random.Random(),
                today=generation_date,
            )
        child_start = (
            1 + int(selection.spouse) + selection.parents
            if selection is not None
            else len(members)
        )
        staged_last_document_paths = render_last_documents(
            members,
            member_identifiers,
            templates_dir=Path(templates_dir),
            coordinates_dir=Path(coordinates_path).parent,
            output_dir=staging_directory / "Docs",
            rng=last_document_rng or random.Random(),
            today=generation_date,
            child_start=child_start,
        )
        os.replace(staging_directory, family_directory)
    except Exception as exc:
        try:
            shutil.rmtree(staging_directory)
        except OSError as cleanup_error:
            raise DocumentGenerationError(
                f"Family generation failed ({exc}); staging cleanup also failed "
                f"for '{staging_directory}': {cleanup_error}"
            ) from cleanup_error
        if isinstance(exc, OSError):
            raise DocumentGenerationError(
                f"Unable to publish generated family in '{family_directory}': {exc}"
            ) from exc
        raise

    published_paths = tuple(
        (
            family_directory / front.relative_to(staging_directory),
            family_directory / back.relative_to(staging_directory),
        )
        for front, back in staged_paths
    )
    published_certificate_paths = tuple(
        family_directory / path.relative_to(staging_directory)
        for path in staged_certificate_paths
    )
    published_list_paths = tuple(
        (
            family_directory / front.relative_to(staging_directory),
            family_directory / back.relative_to(staging_directory),
        )
        for front, back in staged_list_paths
    )
    published_last_document_paths = tuple(
        family_directory / path.relative_to(staging_directory)
        for path in staged_last_document_paths
    )
    return FamilyDocumentResult(
        family_directory,
        published_paths,
        published_certificate_paths,
        published_list_paths,
        published_last_document_paths,
    )