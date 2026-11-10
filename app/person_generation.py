import random
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date

from app.name_database import generate_name, normalize_person_name
from app.person_data import build_deterministic_person_data
from app.schema import CINSchema

MAX_NAME_GENERATION_ATTEMPTS = 32
_CUSTOM_CONSTRAINT_FIELDS = {"name", "date_of_birth", "sex", "naturality"}


class DuplicateGeneratedNameError(ValueError):
    """Raised when a generated or user-provided name is already in use."""


class PersonGenerationError(ValueError):
    """Raised when generated data does not preserve fixed person attributes."""


def _normalize_name(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).split()).casefold()


def _generate_unique_name(
    sex: str,
    names_to_avoid: Sequence[str],
    rng: random.Random | None,
) -> str:
    unavailable = {_normalize_name(name) for name in names_to_avoid}
    for _ in range(MAX_NAME_GENERATION_ATTEMPTS):
        name = generate_name(sex, rng=rng)
        if _normalize_name(name) not in unavailable:
            return name
    raise DuplicateGeneratedNameError(
        "Could not generate a unique name after multiple attempts."
    )


def generate_person(
    recent_names: Sequence[str],
    *,
    constraints: Mapping[str, object] | None = None,
    filiation: str | None = None,
    rng: random.Random | None = None,
) -> CINSchema:
    if not isinstance(recent_names, Sequence) or isinstance(
        recent_names, (str, bytes)
    ):
        raise TypeError("recent_names must be a sequence of names, not a string.")
    if not all(isinstance(name, str) for name in recent_names):
        raise TypeError("Every item in recent_names must be a string.")

    names_to_avoid = [name.strip() for name in recent_names if name.strip()]
    fixed_constraints = dict(constraints or {})
    if isinstance(fixed_constraints.get("sex"), str):
        fixed_constraints["sex"] = str(fixed_constraints["sex"]).strip().upper()
    if isinstance(fixed_constraints.get("name"), str):
        fixed_constraints["name"] = normalize_person_name(
            str(fixed_constraints["name"])
        )
    unsupported_constraints = fixed_constraints.keys() - _CUSTOM_CONSTRAINT_FIELDS
    if unsupported_constraints:
        raise ValueError(
            "Unsupported user-specified generation fields: "
            f"{', '.join(sorted(unsupported_constraints))}."
        )
    if "date_of_birth" in fixed_constraints and not isinstance(
        fixed_constraints["date_of_birth"], date
    ):
        raise TypeError("The fixed date_of_birth constraint must be a date.")
    if any(
        not isinstance(value, str)
        for key, value in fixed_constraints.items()
        if key != "date_of_birth"
    ):
        raise TypeError("Fixed person attributes must be strings or a date.")
    if filiation is not None and not isinstance(filiation, str):
        raise TypeError("The fixed filiation constraint must be a string.")

    recent_name_keys = {_normalize_name(name) for name in names_to_avoid}
    fixed_name = fixed_constraints.get("name")
    if isinstance(fixed_name, str) and _normalize_name(fixed_name) in recent_name_keys:
        raise DuplicateGeneratedNameError(
            "The user-specified name already appears in recent history."
        )

    deterministic = build_deterministic_person_data(fixed_constraints, rng=rng)
    person_name = str(deterministic.fields["name"])
    if (
        "name" not in fixed_constraints
        and _normalize_name(person_name) in recent_name_keys
    ):
        person_name = _generate_unique_name(deterministic.sex, names_to_avoid, rng)

    if filiation is None:
        filiation_names = [person_name, *names_to_avoid]
        mother_name = _generate_unique_name("F", filiation_names, rng)
        filiation_names.append(mother_name)
        father_name = _generate_unique_name("M", filiation_names, rng)
        filiation = f"{mother_name}\n{father_name}"

    person = CINSchema.model_validate(
        {
            **deterministic.fields,
            "name": person_name,
            "filliation": filiation,
        }
    )
    if any(
        getattr(person, field) != expected
        for field, expected in fixed_constraints.items()
    ):
        raise PersonGenerationError(
            "Generated data did not preserve all user-specified attributes."
        )
    return person
