import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.CLI_interface.inner_interface_functions import (
    FamilyMemberInput,
    FamilySelection,
)
from app.person_generation import DuplicateGeneratedNameError, generate_person
from app.name_database import NAME_CONNECTORS
from app.schema import CINSchema


@dataclass(frozen=True)
class GeneratedFamily:
    members: tuple[CINSchema, ...]
    synthetic_names: tuple[str, ...]
    synthetic_parents: tuple[CINSchema, ...] = ()


def generate_family(
    recent_names: Sequence[str],
    selection: FamilySelection,
    *,
    custom_inputs: Sequence[FamilyMemberInput] | None = None,
    parent_sexes: Sequence[str] | None = None,
    rng: random.Random | None = None,
    today: date | None = None,
) -> GeneratedFamily:
    if not isinstance(selection, FamilySelection):
        raise TypeError("selection must be a FamilySelection.")
    if (
        not isinstance(selection.parents, int)
        or isinstance(selection.parents, bool)
        or not 0 <= selection.parents <= 2
        or not isinstance(selection.spouse, bool)
        or not isinstance(selection.children, int)
        or isinstance(selection.children, bool)
        or selection.children < 0
    ):
        raise ValueError("Family selection contains invalid member counts.")

    random_source = rng if rng is not None else random.Random()
    reference_date = today if today is not None else date.today()
    roles = _member_roles(selection)
    if custom_inputs is not None and len(custom_inputs) != len(roles):
        raise ValueError("Custom family input count does not match the selection.")
    if parent_sexes is not None and (
        len(parent_sexes) != selection.parents
        or any(sex not in {"M", "F"} for sex in parent_sexes)
        or (
            len(parent_sexes) == 2
            and parent_sexes[0] == parent_sexes[1]
        )
    ):
        raise ValueError("Parent sexes must match the selection and be opposite.")

    member_keys = [
        _role_key(role, index, roles) for index, role in enumerate(roles)
    ]
    custom_by_role = (
        dict(zip(member_keys, custom_inputs, strict=True))
        if custom_inputs is not None
        else {}
    )
    ages = _resolve_ages(
        roles, member_keys, selection, custom_by_role, random_source, reference_date
    )
    family_names: list[str] = []
    role_by_key = dict(zip(member_keys, roles, strict=True))
    titular_key = "titular"
    spouse_key = "spouse" if selection.spouse else None
    parent_keys = [key for key, role in role_by_key.items() if role == "parent"]
    child_keys = [key for key, role in role_by_key.items() if role == "child"]
    generation_keys = [
        *parent_keys,
        titular_key,
        *([spouse_key] if spouse_key is not None else []),
        *child_keys,
    ]
    records: dict[str, CINSchema] = {}
    synthetic_names: list[str] = []
    synthetic_parents: list[CINSchema] = []

    for member_key in generation_keys:
        role = role_by_key[member_key]
        custom = custom_by_role.get(member_key)
        constraints = (
            custom.generation_constraints(rng=random_source, today=reference_date)
            if custom is not None
            else {}
        )
        if role == "parent" and parent_sexes is not None:
            constraints["sex"] = parent_sexes[parent_keys.index(member_key)]
        constraints["date_of_birth"] = _birth_date_for_age(
            reference_date, ages[member_key]
        )
        filiation = None
        if role == "spouse":
            expected_sex = "M" if records[titular_key].sex == "F" else "F"
            supplied_sex = constraints.get("sex")
            if supplied_sex is not None and supplied_sex != expected_sex:
                raise ValueError(
                    "A generated spouse must be the opposite sex of the titular."
                )
            constraints["sex"] = expected_sex
        if role == "titular" and selection.parents == 2:
            filiation = "\n".join(records[key].name for key in parent_keys)
        elif role == "child":
            if spouse_key is not None:
                filiation = (
                    f"{records[titular_key].name}\n{records[spouse_key].name}"
                )
            else:
                if not synthetic_parents:
                    expected_sex = (
                        "M" if records[titular_key].sex == "F" else "F"
                    )
                    synthetic_parent = generate_person(
                        [*recent_names, *family_names, *synthetic_names],
                        constraints={"sex": expected_sex},
                        rng=random_source,
                    )
                    synthetic_parents.append(synthetic_parent)
                    synthetic_names.append(synthetic_parent.name)
                filiation = (
                    f"{records[titular_key].name}\n{synthetic_parents[0].name}"
                )
        person = generate_person(
            [*recent_names, *family_names, *synthetic_names],
            constraints=constraints,
            filiation=filiation,
            rng=random_source,
        )
        if person.name in family_names:
            raise DuplicateGeneratedNameError(
                "Two family members cannot have the same name."
            )
        _validate_role_name(person.name, role, selection)
        if role == "titular" and selection.parents == 1:
            selected_parent = records[parent_keys[0]]
            existing_lines = _filiation_lines(person)
            unavailable_names = {
                _normalize_name(name)
                for name in (*recent_names, *family_names, *synthetic_names)
            }
            other_name = next(
                (
                    line
                    for line in existing_lines
                    if _normalize_name(line) not in unavailable_names
                    and _normalize_name(line) != _normalize_name(selected_parent.name)
                ),
                None,
            )
            if other_name is None:
                other_name = _generate_synthetic_name(
                    recent_names,
                    family_names,
                    synthetic_names,
                    random_source,
                )
            synthetic_names.append(other_name)
            person = _with_filiation(
                person, f"{selected_parent.name}\n{other_name}"
            )
        family_names.append(person.name)
        records[member_key] = person

    if selection.children:
        child_filiation = (
            f"{records[titular_key].name}\n"
            f"{records[spouse_key].name if spouse_key is not None else synthetic_parents[0].name}"
        )
        for key in child_keys:
            records[key] = _with_filiation(records[key], child_filiation)

    members = tuple(records[key] for key in member_keys)
    return GeneratedFamily(members, tuple(synthetic_names), tuple(synthetic_parents))


def _member_roles(selection: FamilySelection) -> list[str]:
    return (
        ["titular"]
        + (["spouse"] if selection.spouse else [])
        + ["parent"] * selection.parents
        + ["child"] * selection.children
    )


def _birth_date_for_age(reference_date: date, age: int) -> date:
    birth_year = reference_date.year - age
    if birth_year < 1:
        raise ValueError("Age must produce a valid date of birth.")
    try:
        return reference_date.replace(year=birth_year)
    except ValueError:
        return reference_date.replace(year=birth_year, day=28)


def _validate_role_name(name: str, role: str, selection: FamilySelection) -> None:
    word_count = sum(
        word.casefold() not in NAME_CONNECTORS for word in name.split()
    )
    if role == "parent" and word_count != 4:
        raise ValueError(
            "Selected parent names must contain exactly four words, excluding connectors."
        )
    if role in {"titular", "spouse"} and selection.children and word_count < 3:
        raise ValueError(
            "Names used in child filiation must contain at least three words."
        )


def _resolve_ages(
    roles: Sequence[str],
    member_keys: Sequence[str],
    selection: FamilySelection,
    custom_inputs: Mapping[str, FamilyMemberInput],
    rng: random.Random,
    reference_date: date,
) -> dict[str, int]:
    ages: dict[str, int] = {}
    has_children = selection.children > 0

    for role, member_key in zip(roles, member_keys, strict=True):
        fixed_age = custom_inputs[member_key].age if member_key in custom_inputs else None
        if fixed_age is not None and (
            not isinstance(fixed_age, int) or isinstance(fixed_age, bool)
        ):
            raise ValueError("Family member ages must be integers.")
        if role == "titular":
            minimum = 21 if has_children else 1
            maximum = 99 if selection.parents else reference_date.year - 1
            default_minimum, default_maximum = 18, 90
        elif role == "spouse":
            minimum = 21 if has_children else 1
            maximum = reference_date.year - 1
            default_minimum, default_maximum = 18, 90
        elif role == "parent":
            minimum = ages["titular"] + 21
            maximum = 120
            default_minimum, default_maximum = minimum, 120
        else:
            youngest_parent = min(
                ages["titular"],
                ages["spouse"] if selection.spouse else ages["titular"],
            )
            minimum = 1
            maximum = youngest_parent - 20
            default_minimum, default_maximum = 1, maximum

        lower = max(minimum, default_minimum) if fixed_age is None else minimum
        upper = min(maximum, default_maximum) if fixed_age is None else maximum
        if lower > upper:
            raise ValueError("The selected family has incompatible age limits.")
        age = rng.randint(lower, upper) if fixed_age is None else fixed_age
        if role == "titular" and selection.parents and age + 21 > 120:
            raise ValueError(
                "The selected family is infeasible: a parent would exceed 120 years."
            )
        if not minimum <= age <= maximum:
            raise ValueError("A family member's age violates the family age rules.")
        ages[member_key] = age

    return ages


def _role_key(role: str, index: int, roles: Sequence[str]) -> str:
    occurrence = roles[: index + 1].count(role)
    return role if occurrence == 1 else f"{role}_{occurrence}"


def _filiation_lines(person: CINSchema) -> tuple[str, str]:
    lines = tuple(person.filliation.splitlines())
    if len(lines) != 2:
        raise ValueError("Generated filiation must contain exactly two names.")
    return lines[0], lines[1]


def _with_filiation(person: CINSchema, filiation: str) -> CINSchema:
    data = person.model_dump()
    data["filliation"] = filiation
    data["cpf"] = person.cpf.replace(".", "").replace("-", "")[:9]
    return CINSchema.model_validate(data)


def _generate_synthetic_name(
    recent_names: Sequence[str],
    family_names: Sequence[str],
    synthetic_names: Sequence[str],
    rng: random.Random,
) -> str:
    person = generate_person(
        [*recent_names, *family_names, *synthetic_names],
        rng=rng,
    )
    return person.name


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())
