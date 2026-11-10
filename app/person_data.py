import calendar
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from app.schema import CARD_ISSUERS, CPF_REGION_STATES, _add_years, _age_on
from app.name_database import generate_name, normalize_person_name

STATE_CAPITALS = {
    "AC": "Rio Branco",
    "AL": "Maceió",
    "AP": "Macapá",
    "AM": "Manaus",
    "BA": "Salvador",
    "CE": "Fortaleza",
    "DF": "Brasília",
    "ES": "Vitória",
    "GO": "Goiânia",
    "MA": "São Luís",
    "MT": "Cuiabá",
    "MS": "Campo Grande",
    "MG": "Belo Horizonte",
    "PA": "Belém",
    "PB": "João Pessoa",
    "PR": "Curitiba",
    "PE": "Recife",
    "PI": "Teresina",
    "RJ": "Rio de Janeiro",
    "RN": "Natal",
    "RS": "Porto Alegre",
    "RO": "Porto Velho",
    "RR": "Boa Vista",
    "SC": "Florianópolis",
    "SP": "São Paulo",
    "SE": "Aracaju",
    "TO": "Palmas",
}


@dataclass(frozen=True)
class DeterministicPersonData:
    fields: dict[str, object]
    age: int
    sex: str


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _issue_date_window(today: date) -> tuple[date, date]:
    return _add_years(today, -3), _subtract_months(today, 1)


def _naturality_state(value: str) -> str:
    match = re.fullmatch(r"([^/]+)/([A-Z]{2})", value)
    if (
        match is None
        or match.group(2) not in CARD_ISSUERS
        or not match.group(1).strip()
        or match.group(1) != match.group(1).strip()
    ):
        raise ValueError("Naturality must use the format City/valid-2-letter-UF.")
    return match.group(2)


def _date_of_birth_for_age(
    reference_date: date, age: int, rng: random.Random
) -> date:
    earliest = _add_years(reference_date, -(age + 1)) + timedelta(days=1)
    latest = _add_years(reference_date, -age)
    return date.fromordinal(rng.randint(earliest.toordinal(), latest.toordinal()))


def _cpf_stem(state: str, rng: random.Random) -> str:
    region_digit = next(
        digit for digit, states in CPF_REGION_STATES.items() if state in states
    )
    while True:
        stem = "".join(str(rng.randrange(10)) for _ in range(8)) + region_digit
        if len(set(stem)) > 1:
            return stem


def build_deterministic_person_data(
    constraints: Mapping[str, object] | None = None,
    *,
    today: date | None = None,
    rng: random.Random | None = None,
) -> DeterministicPersonData:
    reference_date = today if today is not None else date.today()
    random_source = rng if rng is not None else random.Random()
    fixed = dict(constraints or {})

    if "date_of_birth" in fixed:
        birth_date = fixed["date_of_birth"]
        if not isinstance(birth_date, date):
            raise TypeError("The fixed date_of_birth constraint must be a date.")
        age = _age_on(birth_date, reference_date)
        if age < 1:
            raise ValueError(
                "Custom generation requires an age of at least 1 year; "
                "age zero cannot meet the minimum issue-date window."
            )
    else:
        age = random_source.randint(18, 90)
        birth_date = _date_of_birth_for_age(reference_date, age, random_source)

    sex = fixed.get("sex")
    if sex is None:
        sex = random_source.choice(("M", "F"))
    if isinstance(sex, str):
        sex = sex.strip().upper()
    if sex not in {"M", "F"}:
        raise ValueError("Sex must be either M or F.")
    name = fixed.get("name")
    if name is None:
        name = generate_name(sex, rng=random_source)
    elif isinstance(name, str):
        name = normalize_person_name(name)

    naturality = fixed.get("naturality")
    if naturality is None:
        state = random_source.choice(tuple(STATE_CAPITALS))
        naturality = f"{STATE_CAPITALS[state]}/{state}"
    elif not isinstance(naturality, str):
        raise TypeError("The fixed naturality constraint must be a string.")
    else:
        state = _naturality_state(naturality)

    earliest_issue_date, newest_issue_date = _issue_date_window(reference_date)
    earliest_issue_date = max(earliest_issue_date, birth_date)
    if earliest_issue_date > newest_issue_date:
        raise ValueError(
            "No valid issue date exists between one month and three years "
            "before today and on or after the date of birth."
        )
    issued_date = date.fromordinal(
        random_source.randint(
            earliest_issue_date.toordinal(), newest_issue_date.toordinal()
        )
    )
    validity_years = (
        5 if _age_on(birth_date, issued_date) <= 11 else 10
    )

    fields: dict[str, object] = {
        "cpf": _cpf_stem(state, random_source),
        "sex": sex,
        "date_of_birth": birth_date,
        "nationality": "BRA",
        "naturality": naturality,
        "expirity": _add_years(issued_date, validity_years),
        "card_issuer": CARD_ISSUERS[state],
        "place_of_issue": naturality,
        "issued_date": issued_date,
    }
    fields["name"] = name

    return DeterministicPersonData(fields=fields, age=age, sex=sex)