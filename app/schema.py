import re
from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.name_database import NAME_CONNECTORS, normalize_person_name

CARD_ISSUERS = {
    "AC": "SSP/AC",
    "AL": "SSP/AL",
    "AP": "SSP/AP",
    "AM": "SSP/AM",
    "BA": "SSP/BA",
    "CE": "SSPDS/CE",
    "DF": "SSP/DF",
    "ES": "SESP/ES",
    "GO": "SSP/GO",
    "MA": "SSP/MA",
    "MT": "SESP/MT",
    "MS": "SEJUSP/MS",
    "MG": "PCMG",
    "PA": "SEGUP/PA",
    "PB": "SEDS/PB",
    "PR": "SESP/PR",
    "PE": "SDS/PE",
    "PI": "SSP/PI",
    "RJ": "DETRAN/RJ",
    "RN": "SESED/RN",
    "RS": "IGP/RS",
    "RO": "SESDEC/RO",
    "RR": "SESP/RR",
    "SC": "IGP/SC",
    "SP": "SSP/SP",
    "SE": "SSP/SE",
    "TO": "SSP/TO",
}
CPF_REGION_STATES = {
    "1": {"DF", "GO", "MT", "MS", "TO"},
    "2": {"AC", "AM", "AP", "PA", "RO", "RR"},
    "3": {"CE", "MA", "PI"},
    "4": {"AL", "PB", "PE", "RN"},
    "5": {"BA", "SE"},
    "6": {"MG"},
    "7": {"ES", "RJ"},
    "8": {"SP"},
    "9": {"PR", "SC"},
    "0": {"RS"},
}
DATE_PATTERN = r"^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/[0-9]{4}$"


def _date_json_schema(schema: dict[str, object]) -> None:
    schema.pop("format", None)
    schema["pattern"] = DATE_PATTERN


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError as exc:
            raise ValueError("Date must use the DD/MM/YYYY format.") from exc
    raise ValueError("Date must use the DD/MM/YYYY format.")


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _age_on(birth_date: date, reference_date: date) -> int:
    return reference_date.year - birth_date.year - (
        (reference_date.month, reference_date.day)
        < (birth_date.month, birth_date.day)
    )


def _calculate_cpf_check_digits(first_nine: str) -> str:
    def check_digit(numbers: str, weights: range) -> str:
        remainder = sum(
            int(number) * weight for number, weight in zip(numbers, weights)
        ) % 11
        return "0" if remainder < 2 else str(11 - remainder)

    first = check_digit(first_nine, range(10, 1, -1))
    return first + check_digit(first_nine + first, range(11, 1, -1))


def _valid_cpf_check_digits(digits: str) -> bool:
    return digits[-2:] == _calculate_cpf_check_digits(digits[:9])


class TargetedValidationError(ValueError):
    def __init__(self, message: str, *fields: str) -> None:
        super().__init__(message)
        self.fields = fields


class CINSchema(BaseModel):
    name: str = Field(
        description="Nome completo com iniciais maiúsculas e conectores em minúsculas"
    )
    cpf: str = Field(
        description=(
            "Provide the first nine CPF digits only as a 9-digit string. The "
            "ninth digit must match the naturality state's fiscal region. The "
            "application calculates and validates the two check digits."
        ),
        json_schema_extra={"pattern": r"^[0-9]{9}$"},
    )
    sex: Literal["M", "F"] = Field(description="Sexo: M para Masculino ou F para Feminino")
    date_of_birth: date = Field(
        description="Data de nascimento no formato DD/MM/YYYY",
        json_schema_extra=_date_json_schema,
    )
    nationality: Literal["BRA"] = Field(description="Will always be BRA for Brazilian nationality")
    naturality: str = Field(description="Naturalidade no formato Cidade/UF")
    expirity: date = Field(
        description="Expiração no formato DD/MM/YYYY",
        json_schema_extra=_date_json_schema,
    )
    filliation: str = Field(
        description=(
            "Dois nomes de pais em linhas separadas, cada um com 3 a 4 palavras "
            "significativas, iniciais maiúsculas e conectores em minúsculas"
        ),
        validation_alias=AliasChoices("filiation", "filliation"),
    )
    card_issuer: str
    place_of_issue: str = Field(description="Local de emissão no formato Cidade/UF")
    issued_date: date = Field(
        description="Data de emissão no formato DD/MM/YYYY",
        json_schema_extra=_date_json_schema,
    )

    @field_validator("date_of_birth", "expirity", "issued_date", mode="before")
    @classmethod
    def validate_date_format(cls, value: object) -> date:
        return _parse_date(value)

    @field_validator("sex", mode="before")
    @classmethod
    def normalize_sex(cls, value: object) -> str:
        if isinstance(value, str):
            value = value.strip().upper()
        if value not in {"M", "F"}:
            raise ValueError("Sex must be either M or F.")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        words = value.split()
        if value != value.strip():
            raise ValueError("Name must not have surrounding whitespace.")
        significant_words = [
            word for word in words if word.casefold() not in NAME_CONNECTORS
        ]
        if not 1 <= len(significant_words) <= 4:
            raise ValueError("Name must contain 2 to 4 significant words.")
        return normalize_person_name(value)

    @field_validator("cpf", mode="before")
    @classmethod
    def generate_cpf_check_digits(cls, value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{9}", value):
            raise ValueError("CPF stem must contain exactly nine digits.")
        if len(set(value)) == 1:
            raise ValueError("CPF stem cannot use repeated digits.")

        digits = value + _calculate_cpf_check_digits(value)
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        if not re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", value):
            raise ValueError("CPF must use the format 000.000.000-00.")
        digits = value.replace(".", "").replace("-", "")
        if len(set(digits)) == 1 or not _valid_cpf_check_digits(digits):
            raise ValueError("CPF check digits are invalid.")
        return value

    @field_validator("naturality", "place_of_issue")
    @classmethod
    def validate_city_state(cls, value: str) -> str:
        match = re.fullmatch(r"([^/]+)/([A-Z]{2})", value)
        if not match or not match.group(1).strip() or match.group(1) != match.group(1).strip():
            raise ValueError("Value must use the format City/UF with an uppercase two-letter UF.")
        if match.group(2) not in CARD_ISSUERS:
            raise ValueError("UF must be a valid Brazilian federative unit.")
        return value

    @field_validator("filliation")
    @classmethod
    def validate_filiation(cls, value: str) -> str:
        parents = value.splitlines()
        if len(parents) != 2:
            raise ValueError("Filiation must contain exactly two names on separate lines.")
        normalized_parents: list[str] = []
        for parent in parents:
            words = parent.split()
            if parent != parent.strip():
                raise ValueError("Each parent name must not have surrounding whitespace.")
            significant_words = [
                word for word in words if word.casefold() not in NAME_CONNECTORS
            ]
            if not 3 <= len(significant_words) <= 4:
                raise ValueError(
                    "Each parent name must contain 3 to 4 significant words."
                )
            normalized_parents.append(normalize_person_name(parent))
        return "\n".join(normalized_parents)

    @model_validator(mode="after")
    def validate_related_fields(self) -> "CINSchema":
        naturality_match = re.fullmatch(r"([^/]+)/([A-Z]{2})", self.naturality)
        if naturality_match is None:
            raise TargetedValidationError(
                "Naturality must use the format City/UF.", "naturality"
            )
        naturality_uf = naturality_match.group(2)
        cpf_region = self.cpf.replace(".", "").replace("-", "")[8]
        if naturality_uf not in CPF_REGION_STATES[cpf_region]:
            raise TargetedValidationError(
                "CPF regional digit does not match the naturality state.", "cpf"
            )
        if self.card_issuer != CARD_ISSUERS[naturality_uf]:
            raise TargetedValidationError(
                "Card issuer does not match the naturality state.", "card_issuer"
            )

        today = date.today()
        if self.date_of_birth > today:
            raise TargetedValidationError(
                "Date of birth cannot be in the future.", "date_of_birth"
            )
        if self.issued_date < _add_years(today, -3) or self.issued_date > today:
            raise TargetedValidationError(
                "Issue date must be within the previous three years.", "issued_date"
            )
        if self.issued_date < self.date_of_birth:
            raise TargetedValidationError(
                "Issue date cannot be before date of birth.", "issued_date"
            )

        validity_years = 5 if _age_on(self.date_of_birth, self.issued_date) <= 11 else 10
        if self.expirity != _add_years(self.issued_date, validity_years):
            raise TargetedValidationError(
                f"Expiry date must be exactly {validity_years} years after issue date.",
                "expirity",
            )
        return self
