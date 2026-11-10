from __future__ import annotations

import random
import shutil
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.CLI_interface.inner_interface_functions import (
    FamilySelection,
)
from app.family_generation import generate_family
from app.history import record_names
from app.pillow import DocumentGenerationError, generate_family_documents
from app.pillow.document_editor import _folder_name
from app.schema import CINSchema


@dataclass(frozen=True)
class BatchFamilySummary:
    family_directory: Path
    selection: FamilySelection
    member_count: int
    titular_name: str
    titular_age: int
    members: tuple[CINSchema, ...]


@dataclass(frozen=True)
class BatchGenerationResult:
    batch_directory: Path
    families: tuple[BatchFamilySummary, ...]
    readme_path: Path


def generate_batch_families(
    count: int,
    *,
    recent_names: Sequence[str] | None = None,
    output_dir: str | Path = "output",
    rng: random.Random | None = None,
    today: date | None = None,
) -> BatchGenerationResult:
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("Batch size must be positive.")

    source_rng = rng if rng is not None else random.Random()
    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    families: list[BatchFamilySummary] = []
    names = list(recent_names or [])
    generated_names: list[str] = []
    temp_directory = base_dir / f"_{count}_batch_{uuid.uuid4().hex}"
    temp_directory.mkdir(parents=True, exist_ok=True)
    owned_directory = temp_directory

    try:
        for _ in range(count):
            selection, parent_sexes = _build_batch_selection(source_rng)
            family = generate_family(
                names,
                selection,
                parent_sexes=parent_sexes,
                rng=source_rng,
                today=today,
            )
            documents = generate_family_documents(
                family.members,
                selection=selection,
                synthetic_parents=family.synthetic_parents,
                output_dir=temp_directory,
                today=today,
            )
            renamed_directory = _rename_family_directory(
                documents.family_directory, family, selection, today=today
            )
            families.append(
                BatchFamilySummary(
                    family_directory=renamed_directory,
                    selection=selection,
                    member_count=len(family.members) - 1,
                    titular_name=family.members[0].name,
                    titular_age=_age_on(
                        family.members[0].date_of_birth, today or date.today()
                    ),
                    members=family.members,
                )
            )
            names.extend(member.name for member in family.members)
            generated_names.extend(member.name for member in family.members)

        final_directory = base_dir / _batch_directory_name(count, families)
        readme_path = temp_directory / "_README.txt"
        readme_path.write_text(_build_readme(families, today=today), encoding="utf-8")
        temp_directory.rename(final_directory)
        owned_directory = final_directory
        families = [
            BatchFamilySummary(
                family_directory=final_directory
                / family.family_directory.relative_to(temp_directory),
                selection=family.selection,
                member_count=family.member_count,
                titular_name=family.titular_name,
                titular_age=family.titular_age,
                members=family.members,
            )
            for family in families
        ]
        record_names(generated_names)
    except Exception as exc:
        if owned_directory.exists():
            try:
                shutil.rmtree(owned_directory)
            except OSError as cleanup_error:
                raise DocumentGenerationError(
                    f"Batch generation failed ({exc}); could not remove "
                    f"partial batch '{owned_directory}': {cleanup_error}"
                ) from cleanup_error
        raise

    return BatchGenerationResult(
        batch_directory=final_directory,
        families=tuple(families),
        readme_path=final_directory / "_README.txt",
    )


def _build_batch_selection(
    rng: random.Random,
) -> tuple[FamilySelection, tuple[str, ...]]:
    parent_count = 0
    parent_sexes: tuple[str, ...] = ()
    if rng.random() < 0.75:
        parent_count = 1
        first_sex = rng.choice(("M", "F"))
        parent_sexes = (first_sex,)
        if rng.random() < 0.75:
            parent_count = 2
            parent_sexes = (first_sex, "F" if first_sex == "M" else "M")

    spouse = False
    if rng.random() < 0.75:
        spouse = True

    if not spouse:
        return FamilySelection(parents=parent_count, spouse=False, children=0), parent_sexes

    children = 0
    chance = 0.75
    if rng.random() < 0.75:
        children += 1
    while rng.random() < chance:
        children += 1
        chance *= 0.5
        if chance < 0.01:
            break
    return (
        FamilySelection(parents=parent_count, spouse=True, children=children),
        parent_sexes,
    )


def _age_on(birth_date: date, today: date) -> int:
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _rename_family_directory(
    family_directory: Path,
    family,
    selection: FamilySelection,
    *,
    today: date | None = None,
) -> Path:
    titular = family.members[0]
    folder_name = (
        f"M={len(family.members)-1}_{_folder_name(titular.name)}_"
        f"{_age_on(titular.date_of_birth, today or date.today())}_P={selection.parents}_"
        f"C={1 if selection.spouse else 0}_F={selection.children}_{uuid.uuid4().hex}"
    )
    target = family_directory.parent / folder_name
    if family_directory != target:
        family_directory.rename(target)
    return target


def _batch_directory_name(count: int, families: Sequence[BatchFamilySummary]) -> str:
    if not families:
        return f"_{count}_Batch_{uuid.uuid4().hex}"
    largest = max(families, key=lambda item: item.member_count)
    return f"_{count}_{_folder_name(largest.titular_name)}_{uuid.uuid4().hex}"


def _build_readme(
    families: Sequence[BatchFamilySummary], *, today: date | None = None
) -> str:
    ordered = sorted(families, key=lambda family: family.member_count, reverse=True)
    lines = [
        "Esse documento serve como um resumo de todas as famílias criadas\n\n",
        f"Foram geradas {len(ordered)} famílias, da maior para a menor:\n\n",
    ]
    divider = "=" * 114
    for family in ordered:
        members = _summarize_family(family, today=today)
        lines.append(f"{divider}\n")
        lines.append(f"Família do {family.titular_name}:\n\n")
        lines.append(f"Membros gerados: {family.member_count}\n\n")
        lines.append("Pais gerados:\n")
        lines.extend(_format_entries(members["parents"]))
        lines.append("\nCônjugue gerado:\n")
        lines.extend(_format_entries(members["spouse"]))
        lines.append("\nFilhos gerados:\n")
        lines.extend(_format_entries(members["children"]))
        lines.append("\n")
    lines.append(f"{divider}\n")
    return "".join(lines)


def _summarize_family(
    family: BatchFamilySummary, *, today: date | None = None
) -> dict[str, list[str]]:
    members = tuple(family.members)
    spouse_member = members[1] if family.selection.spouse and len(members) > 1 else None
    parent_start = 1 + int(family.selection.spouse)
    parent_members = members[parent_start : parent_start + family.selection.parents]
    child_members = members[parent_start + family.selection.parents :]
    today = today or date.today()

    parents = [
        f"{person.name}, {_age_on(person.date_of_birth, today)} anos."
        for person in parent_members
    ]
    spouse = [
        f"{spouse_member.name}, {_age_on(spouse_member.date_of_birth, today)} anos."
    ] if spouse_member is not None else []
    children = [
        f"{person.name}, {_age_on(person.date_of_birth, today)} anos."
        for person in child_members
    ]
    return {"parents": parents, "spouse": spouse, "children": children}


def _format_entries(entries: Sequence[str]) -> list[str]:
    if not entries:
        return [" - Nenhum gerado\n"]
    return [f" - {entry}\n" for entry in entries]
