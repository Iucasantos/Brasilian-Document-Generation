import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from app.CLI_interface.interface_formation import (
    clear_screen,
    display_page,
    prompt_page,
)
from app.CLI_interface.errors import (
    InputRetryLimitError,
    MAX_INVALID_INPUT_ATTEMPTS,
)
from app.name_database import (
    NAME_CONNECTORS,
    complete_custom_name,
)
from app.person_data import STATE_CAPITALS
from app.schema import CARD_ISSUERS

_Value = TypeVar("_Value")


class InvalidInputError(ValueError):
    def __init__(self, message: str, *, syntax: bool = False) -> None:
        super().__init__(message)
        self.syntax = syntax


@dataclass(frozen=True)
class CustomGenerationInput:
    name: str
    age: int
    sex: str
    state: str
    city: str
    date_of_birth: date

    def generation_constraints(self) -> dict[str, object]:
        return {
            "name": self.name,
            "date_of_birth": self.date_of_birth,
            "sex": self.sex,
            "naturality": f"{self.city}/{self.state}",
        }


@dataclass(frozen=True)
class FamilySelection:
    parents: int = 0
    spouse: bool = False
    children: int = 0

    @property
    def relative_count(self) -> int:
        return self.parents + int(self.spouse) + self.children


@dataclass(frozen=True)
class FamilyMemberInput:
    name: str | None
    age: int
    sex: str | None
    state: str | None
    city: str | None

    def generation_constraints(
        self,
        *,
        rng: random.Random | None = None,
        today: date | None = None,
    ) -> dict[str, object]:
        random_source = rng if rng is not None else random.Random()
        reference_date = today if today is not None else date.today()
        birth_year = reference_date.year - self.age
        try:
            birth_date = reference_date.replace(year=birth_year)
        except ValueError:
            birth_date = reference_date.replace(year=birth_year, day=28)

        constraints: dict[str, object] = {"date_of_birth": birth_date}
        if self.name is not None:
            constraints["name"] = complete_custom_name(self.name)
        if self.sex is not None:
            constraints["sex"] = self.sex

        state = self.state
        city = self.city
        if state is None and city is not None:
            state = random_source.choice(tuple(STATE_CAPITALS))
        if state is not None:
            naturality_city = city if city is not None else STATE_CAPITALS[state]
            constraints["naturality"] = f"{naturality_city}/{state}"
        return constraints


def _check_syntax(value: str) -> None:
    if any(
        not (
            character.isalpha()
            or character.isdigit()
            or character.isspace()
            or character == "-"
        )
        for character in value
    ):
        raise InvalidInputError("Invalid syntax!", syntax=True)


def _validate_name(
    value: str, *, min_words: int = 1, max_words: int = 4
) -> str:
    value = value.strip()
    _check_syntax(value)
    if any(character.isdigit() for character in value) or "-" in value:
        raise InvalidInputError("Invalid data!")
    words = value.split()
    significant_words = [
        word for word in words if word.casefold() not in NAME_CONNECTORS
    ]
    if not 1 <= len(significant_words) <= max_words:
        raise InvalidInputError("Invalid data!")
    normalized = complete_custom_name(value)
    significant_words = [
        word for word in normalized.split() if word.casefold() not in NAME_CONNECTORS
    ]
    if not min_words <= len(significant_words) <= max_words:
        raise InvalidInputError("Invalid data!")
    return normalized


def _validate_age(value: str, *, today: date) -> tuple[int, date]:
    value = value.strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value) and "." in value:
        raise InvalidInputError("Invalid data!")
    if value.startswith("-") and value[1:].isdecimal():
        raise InvalidInputError("Invalid data!")
    _check_syntax(value)
    if not value.isdecimal():
        raise InvalidInputError("Invalid data!")
    age = int(value)
    if age == 0:
        raise InvalidInputError(
            "Age must be at least 1 year; age zero cannot meet the issue-date rules."
        )
    birth_year = today.year - age
    if birth_year < 1:
        raise InvalidInputError("Invalid data!")
    try:
        birth_date = today.replace(year=birth_year)
    except ValueError:
        birth_date = today.replace(year=birth_year, day=28)
    return age, birth_date


def _validate_sex(value: str) -> str:
    value = value.strip()
    _check_syntax(value)
    normalized = value.upper()
    if normalized not in {"M", "F"}:
        raise InvalidInputError("Invalid data!")
    return normalized


def _validate_state(value: str) -> str:
    value = value.strip().upper()
    _check_syntax(value)
    if value not in CARD_ISSUERS:
        raise InvalidInputError("Invalid data!")
    return value


def _validate_city(value: str) -> str:
    value = " ".join(value.strip().split())
    _check_syntax(value)
    if any(character.isdigit() for character in value):
        raise InvalidInputError("Invalid data!")
    if not value or not any(character.isalpha() for character in value):
        raise InvalidInputError("Invalid data!")
    return value


def _validate_batch_size(value: str) -> int:
    text = value.strip()
    if not text:
        return 10
    if any(character.isalpha() for character in text):
        raise InvalidInputError("Invalid data!")
    if text.startswith("-") and text[1:].isdigit():
        raise InvalidInputError("Invalid data!")
    if not text.isdigit():
        raise InvalidInputError("Invalid syntax!", syntax=True)
    count = int(text)
    if count <= 0:
        raise InvalidInputError("Invalid data!")
    return count


def prompt_batch_size(
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    return _prompt_validated(
        "Quantas famílias deseja gerar?",
        _validate_batch_size,
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
        error_delay=2,
    )


def _prompt_validated(
    question: str,
    validator: Callable[[str], _Value],
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None],
    sleep_fn: Callable[[float], None],
    error_delay: float = 3,
) -> _Value:
    for _ in range(MAX_INVALID_INPUT_ATTEMPTS):
        raw_value = prompt_page(
            question,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        try:
            return validator(raw_value)
        except InvalidInputError as exc:
            display_page(
                "Invalid syntax!" if exc.syntax else str(exc),
                output_fn=output_fn,
            )
            sleep_fn(error_delay)
    display_page("Too many invalid attempts. Returning to menu.", output_fn=output_fn)
    raise InputRetryLimitError(
        f"Input for '{question}' remained invalid after "
        f"{MAX_INVALID_INPUT_ATTEMPTS} attempts."
    )


def collect_custom_generation_input(
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
    today: date | None = None,
) -> CustomGenerationInput:
    reference_date = today if today is not None else date.today()
    name = _prompt_validated(
        "What's the name?",
        _validate_name,
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
    )
    age, birth_date = _prompt_validated(
        "What's the age (in years)?",
        lambda value: _validate_age(value, today=reference_date),
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
    )
    sex = _prompt_validated(
        "What's the sex?",
        _validate_sex,
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
    )
    state = _prompt_validated(
        "What's the state (UF)?",
        _validate_state,
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
    )
    city = _prompt_validated(
        "What's the city?",
        _validate_city,
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
    )
    return CustomGenerationInput(
        name=name,
        age=age,
        sex=sex,
        state=state,
        city=city,
        date_of_birth=birth_date,
    )


def select_family_members(
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> FamilySelection:
    parents = 0
    spouse = False
    children = 0
    for _ in range(MAX_INVALID_INPUT_ATTEMPTS):
        clear_options = [
            f"{_menu_option('1 - Add Parent', parents == 2)}",
            f"{_menu_option('2 - Add Spouse', spouse)}",
            f"{_menu_option('3 - Add Son', False)}",
            "4 - Clear all",
            "5 - Proceed",
        ]
        clear_screen()
        output_fn("=" * 43)
        for option in clear_options:
            output_fn(option)
        output_fn("=" * 43)
        if parents or spouse or children:
            members = []
            if parents:
                members.append(f"{parents} Parent" + ("s" if parents != 1 else ""))
            if spouse:
                members.append("1 Spouse")
            if children:
                members.append(f"{children} Son" + ("s" if children != 1 else ""))
            output_fn(f"Current family: {', '.join(members)}")
        output_fn(">> ", end="", flush=True)
        choice = input_fn().strip()

        if choice == "1":
            if parents == 2:
                _show_family_error("Option Limit Reached!", output_fn, sleep_fn)
            else:
                parents += 1
        elif choice == "2":
            if spouse:
                _show_family_error("Option Limit Reached!", output_fn, sleep_fn)
            else:
                spouse = True
        elif choice == "3":
            children += 1
        elif choice == "4":
            parents = 0
            spouse = False
            children = 0
        elif choice == "5":
            return FamilySelection(parents, spouse, children)
        else:
            _show_family_error("Invalid data!", output_fn, sleep_fn)
    display_page(
        "Too many invalid attempts. Returning to menu.",
        output_fn=output_fn,
    )
    raise InputRetryLimitError(
        f"Family selection remained invalid after "
        f"{MAX_INVALID_INPUT_ATTEMPTS} attempts."
    )


def _menu_option(label: str, limit_reached: bool) -> str:
    if not limit_reached:
        return label
    gray = "\033[38;2;134;142;150m"
    reset = "\033[0m"
    return f"{gray}{label}{reset} (Max Limit Reached)"


def _show_family_error(
    message: str,
    output_fn: Callable[..., None],
    sleep_fn: Callable[[float], None],
) -> None:
    display_page(message, output_fn=output_fn)
    sleep_fn(3)


def collect_custom_family_member_input(
    role: str,
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
    min_age: int | None = None,
    max_age: int | None = None,
    name_min_words: int = 2,
    name_max_words: int = 4,
    rng: random.Random | None = None,
) -> FamilyMemberInput:
    random_source = rng if rng is not None else random.Random()

    def prompt_optional(
        question: str, validator: Callable[[str], _Value]
    ) -> _Value | None:
        def validate_or_blank(value: str) -> _Value | None:
            if not value.strip():
                return None
            return validator(value)

        return _prompt_validated(
            question,
            validate_or_blank,
            input_fn=input_fn,
            output_fn=output_fn,
            sleep_fn=sleep_fn,
        )

    name = prompt_optional(
        f"What's the name for {role}?",
        lambda value: _validate_name(
            value, min_words=name_min_words, max_words=name_max_words
        ),
    )

    age_question = "What's the age (in years)?"
    if min_age is not None:
        age_question += f"(Min age {min_age})"
    if max_age is not None:
        age_question += f"(Max age {max_age})"

    def validate_age(value: str) -> int:
        age, _ = _validate_age(value, today=date.today())
        if min_age is not None and age < min_age:
            raise InvalidInputError("Invalid data!")
        if max_age is not None and age > max_age:
            raise InvalidInputError("Invalid data!")
        return age

    age = prompt_optional(age_question, validate_age)
    if age is None:
        lower_bound = min_age if min_age is not None else 18
        upper_bound = max_age if max_age is not None else 90
        if lower_bound > upper_bound:
            raise InvalidInputError("Invalid data!")
        age = random_source.randint(lower_bound, upper_bound)

    sex = prompt_optional("What's the sex (M or F)?", _validate_sex)
    state = prompt_optional("What's the state (UF)?", _validate_state)
    city = prompt_optional("What's the city?", _validate_city)
    return FamilyMemberInput(
        name=name,
        age=age,
        sex=sex,
        state=state,
        city=city,
    )


def collect_custom_family_inputs(
    selection: FamilySelection,
    *,
    input_fn: Callable[[], str],
    output_fn: Callable[..., None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[FamilyMemberInput, ...]:
    members: list[FamilyMemberInput] = []
    titular = collect_custom_family_member_input(
        "titular",
        input_fn=input_fn,
        output_fn=output_fn,
        sleep_fn=sleep_fn,
        min_age=21 if selection.children else None,
        max_age=99 if selection.parents else None,
        name_min_words=3 if selection.children else 2,
    )
    members.append(titular)

    spouse: FamilyMemberInput | None = None
    if selection.spouse:
        spouse = collect_custom_family_member_input(
            "spouse",
            input_fn=input_fn,
            output_fn=output_fn,
            sleep_fn=sleep_fn,
            min_age=21 if selection.children else None,
            name_min_words=3 if selection.children else 2,
        )
        members.append(spouse)

    for parent_number in range(selection.parents):
        members.append(
            collect_custom_family_member_input(
                f"parent {parent_number + 1}",
                input_fn=input_fn,
                output_fn=output_fn,
                sleep_fn=sleep_fn,
                min_age=titular.age + 21,
                max_age=120,
                name_min_words=4,
                name_max_words=4,
            )
        )

    youngest_parent_age = min(
        titular.age,
        spouse.age if spouse is not None else titular.age,
    )
    max_child_age = youngest_parent_age - 20
    for child_number in range(selection.children):
        if max_child_age < 1:
            raise InvalidInputError("Invalid data!")
        members.append(
            collect_custom_family_member_input(
                f"son {child_number + 1}",
                input_fn=input_fn,
                output_fn=output_fn,
                sleep_fn=sleep_fn,
                min_age=1,
                max_age=max_child_age,
            )
        )
    return tuple(members)
