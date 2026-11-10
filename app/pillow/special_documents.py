import random
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFont

from app.CLI_interface.inner_interface_functions import FamilySelection
from app.schema import CINSchema, _add_years, _age_on

from .document_editor import (
    DocumentGenerationError,
    _folder_name,
)

CASA_FIELDS = {
    "nome_tit",
    "cpf_tit",
    "nome_spouse",
    "cpf_spouse",
    "matricula_casa",
    "full_info",
    "data_reg",
    "dia_casa",
    "mes_casa",
    "ano_casa",
    "reg_casa",
    "nomes_casa",
    "averbacoes",
    "num_tit",
    "data_tit",
    "val_tit",
    "num_spouse",
    "data_spouse",
    "val_spouse",
}
NASCI_FIELDS = {
    "name_cer",
    "cpf_cer",
    "matricula_cer",
    "data_nas",
    "dia_cer",
    "mes_cer",
    "ano_cer",
    "hor_nas",
    "municipio_cer",
    "uf_cer",
    "local_nas",
    "municipio_nas",
    "uf_nas",
    "sexo_nas",
    "pai_nome",
    "muni_pai",
    "uf_pai",
    "avos_pai",
    "mae_nome",
    "muni_mae",
    "uf_mae",
    "avos_mae",
    "gemeo",
    "data_registro",
    "dnv",
    "averbacoes",
    "anotacoes",
}
FONT_PATHS = (
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/Calibri.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/calibri.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Calibri.ttf",
)
MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
TEST_CPF_TITULAR = "TESTE-CPF-TIT"
TEST_CPF_CONJUGE = "TESTE-CPF-CONJ"
TEST_CPF_FILHO = "TESTE-CPF-FIL"
TEST_NUM_TITULAR = "TESTE-NUM-TIT"
TEST_NUM_CONJUGE = "TESTE-NUM-CONJ"
TEST_DNV = "TESTE-DNV"
FIELD_ALIASES = {"nome_cer": "name_cer", "emissao": "emissão"}
LAST_DOCUMENT_FIELDS = {
    "local", "le_an", "le_at", "le_pro", "mes_ano", "ven",
    "nome", "nome_1", "cpf", "cpf_0", "emissão", "referencia", "vencim",
}
LAST_DOCUMENT_FONT_SIZES = {
    "le_an": 13, "le_at": 13, "le_pro": 13, "mes_ano": 13, "ven": 13,
    "nome_1": 10, "cpf": 10,
    "local": 8, "nome": 8, "cpf_0": 8, "emissão": 8,
    "referencia": 8, "vencim": 8,
}
CALIBRI_BOLD_FONT_PATHS = (
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/Calibri Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Calibri_Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/calibrib.ttf",
)
DIV_TEST_MIN = 10_000_000
DIV_TEST_MAX = 99_999_999
TEST_REGISTRATION_NUMBER_MIN = 100_000_000_000_000_000_000_000_000
TEST_REGISTRATION_NUMBER_MAX = 999_999_999_999_999_999_999_999_999   

def _numeric_test_registration(rng: random.Random) -> str:
    return str(
        rng.randrange(TEST_REGISTRATION_NUMBER_MIN, TEST_REGISTRATION_NUMBER_MAX)
    )

def _numeric_dnv(rng: random.Random) -> str:
    return str(
        rng.randrange(DIV_TEST_MIN, DIV_TEST_MAX)
    )


def number_to_portuguese_words(value: int) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 9999:
        raise ValueError("Number must be an integer from 0 to 9999.")

    units = (
        "zero",
        "um",
        "dois",
        "três",
        "quatro",
        "cinco",
        "seis",
        "sete",
        "oito",
        "nove",
    )
    teens = (
        "dez",
        "onze",
        "doze",
        "treze",
        "quatorze",
        "quinze",
        "dezesseis",
        "dezessete",
        "dezoito",
        "dezenove",
    )
    tens = (
        "",
        "",
        "vinte",
        "trinta",
        "quarenta",
        "cinquenta",
        "sessenta",
        "setenta",
        "oitenta",
        "noventa",
    )
    hundreds = (
        "",
        "cento",
        "duzentos",
        "trezentos",
        "quatrocentos",
        "quinhentos",
        "seiscentos",
        "setecentos",
        "oitocentos",
        "novecentos",
    )

    def under_thousand(number: int) -> str:
        if number < 10:
            return units[number]
        if number < 20:
            return teens[number - 10]
        if number < 100:
            ten, unit = divmod(number, 10)
            return tens[ten] if unit == 0 else f"{tens[ten]} e {units[unit]}"
        if number == 100:
            return "cem"
        hundred, remainder = divmod(number, 100)
        prefix = hundreds[hundred]
        return (
            prefix
            if remainder == 0
            else f"{prefix} e {under_thousand(remainder)}"
        )

    if value < 1000:
        return under_thousand(value)
    thousands, remainder = divmod(value, 1000)
    prefix = "mil" if thousands == 1 else f"{under_thousand(thousands)} mil"
    if remainder == 0:
        return prefix
    conjunction = " e " if remainder < 100 or remainder == 100 else " "
    return f"{prefix}{conjunction}{under_thousand(remainder)}"


def format_long_date(value: date) -> str:
    return (
        f"{number_to_portuguese_words(value.day)} de {MONTHS[value.month - 1]} "
        f"de {number_to_portuguese_words(value.year)}"
    )


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    day = min(value.day, (next_month - timedelta(days=1)).day)
    return date(year, month, day)


def build_last_document_fields(
    person: CINSchema,
    *,
    rng: random.Random,
    today: date,
) -> dict[str, str]:
    earliest_issue_date = _shift_month(today, -2)
    issue_date = date.fromordinal(
        rng.randint(earliest_issue_date.toordinal(), today.toordinal())
    )
    previous_month = _shift_month(issue_date, -1)
    expiry_date = previous_month + timedelta(days=10)
    month_year = previous_month.strftime("%m/%Y")
    return {
        "local": person.naturality,
        "le_an": previous_month.strftime("%d/%m/%Y"),
        "le_at": issue_date.strftime("%d/%m/%Y"),
        "le_pro": _shift_month(previous_month, 1).strftime("%d/%m/%Y"),
        "mes_ano": month_year,
        "ven": expiry_date.strftime("%d/%m/%Y"),
        "nome": person.name.upper(),
        "nome_1": person.name.upper(),
        "cpf": person.cpf,
        "cpf_0": person.cpf,
        "emissão": issue_date.strftime("%d/%m/%Y"),
        "referencia": month_year,
        "vencim": expiry_date.strftime("%d/%m/%Y"),
    }


def render_last_documents(
    members: Sequence[CINSchema],
    member_identifiers: Sequence[str],
    *,
    templates_dir: Path,
    coordinates_dir: Path,
    output_dir: Path,
    rng: random.Random,
    today: date,
    child_start: int,
) -> tuple[Path, ...]:
    if len(members) != len(member_identifiers):
        raise DocumentGenerationError(
            "Last-document member identifiers do not match the generated family."
        )
    generated_paths: list[Path] = []
    for index, person in enumerate(members):
        if index >= child_start and _age_on(person.date_of_birth, today) <= 22:
            continue
        fields = build_last_document_fields(person, rng=rng, today=today)
        destination = (
            Path(output_dir)
            / f"{_folder_name(person.name.split()[0])}_{member_identifiers[index]}.png"
        )
        _render_last_document(
            fields,
            destination,
            template_path=Path(templates_dir) / "comres.png",
            coordinates_path=Path(coordinates_dir) / "comres.xml",
        )
        generated_paths.append(destination)
    return tuple(generated_paths)


def _calibri_bold_font(size: int) -> ImageFont.FreeTypeFont:
    for font_path in CALIBRI_BOLD_FONT_PATHS:
        try:
            font = ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
        if font.getname()[0].casefold() == "calibri":
            return font
    raise DocumentGenerationError(
        "Calibri bold is unavailable. Install Calibri or configure its font path."
    )


def _render_last_document(
    values: Mapping[str, str],
    destination: Path,
    *,
    template_path: Path,
    coordinates_path: Path,
) -> None:
    if set(values) != LAST_DOCUMENT_FIELDS:
        raise DocumentGenerationError("Invalid last-document data fields.")
    expected_size, fields = _load_certificate_coordinates(
        coordinates_path, LAST_DOCUMENT_FIELDS
    )
    try:
        with Image.open(template_path) as source:
            source.load()
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise DocumentGenerationError(
            f"Unable to open last-document template '{template_path}': {exc}"
        ) from exc

    try:
        if image.size != expected_size:
            raise DocumentGenerationError(
                f"Last-document template '{template_path}' has dimensions "
                f"{image.size}, expected {expected_size}."
            )
        draw = ImageDraw.Draw(image)
        for field_name, rectangle in fields.items():
            text = values[field_name]
            preferred_size = LAST_DOCUMENT_FONT_SIZES[field_name]
            bold = field_name in {"le_an", "le_at", "le_pro", "mes_ano", "ven"}
            color = "#005275" if field_name == "local" else "#101010"
            for size in range(preferred_size, 4, -1):
                font = _calibri_bold_font(size) if bold else _calibri_font(size)
                padding = 1
                try:
                    lines = _wrapped_lines(
                        draw,
                        text,
                        rectangle["width"] - 2 * padding,
                        font,
                        field_name=field_name,
                    )
                except DocumentGenerationError:
                    continue
                if field_name == "nome" and len(lines) > 2:
                    continue
                line_bbox = draw.textbbox((0, 0), "Ag", font=font)
                line_height = max(1, line_bbox[3] - line_bbox[1])
                if line_height * len(lines) <= rectangle["height"] - 2 * padding:
                    break
            else:
                raise DocumentGenerationError(
                    f"Text cannot fit last-document field '{field_name}'."
                )
            centered = field_name in {
                "le_at",
                "le_an",
                "le_pro",
                "mes_ano",
                "ven",
            }
            content_height = line_height * len(lines)
            y = (
                rectangle["y"]
                + max(padding, (rectangle["height"] - content_height) // 2)
                if centered
                else rectangle["y"] + padding
            )
            for line in lines:
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                x = (
                    rectangle["x"]
                    + (rectangle["width"] - line_width) // 2
                    - line_bbox[0]
                    if centered
                    else rectangle["x"] + padding
                )
                draw.text(
                    (x, y - line_bbox[1]),
                    line,
                    fill=color,
                    font=font,
                )
                y += line_height
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG")
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to save last-document image '{destination}': {exc}"
        ) from exc
    finally:
        image.close()


def build_marriage_fields(
    titular: CINSchema,
    spouse: CINSchema,
    *,
    rng: random.Random,
    today: date,
) -> dict[str, str]:
    if titular.sex == spouse.sex:
        raise DocumentGenerationError(
            "Marriage mockups require the spouse to be the opposite sex of the titular."
        )
    threshold = _add_years(
        max(titular.date_of_birth, spouse.date_of_birth),
        21,
    )
    if threshold > today:
        raise DocumentGenerationError(
            "No valid marriage registration date exists after both spouses turn 21."
        )
    registration_date = date.fromordinal(
        rng.randint(threshold.toordinal(), today.toordinal())
    )
    return {
        "nome_tit": titular.name,
        "cpf_tit": titular.cpf,
        "nome_spouse": spouse.name,
        "cpf_spouse": spouse.cpf,
        "matricula_casa": str(_numeric_test_registration(rng)).center(20),
        "full_info": "",
        "data_reg": format_long_date(registration_date),
        "dia_casa": f"{registration_date.day:02d}",
        "mes_casa": f"{registration_date.month:02d}",
        "ano_casa": f"{registration_date.year:04d}",
        "reg_casa": "comunhão parcial de bens",
        "nomes_casa": (
            f"o cônjuge passou a assinar: {titular.name}\n"
            f"o cônjuge passou a assinar: {spouse.name}"
        ),
        "averbacoes": "nada consta",
        "num_tit": titular.cpf,
        "data_tit": titular.issued_date.strftime("%d/%m/%Y"),
        "val_tit": titular.expirity.strftime("%d/%m/%Y"),
        "num_spouse": spouse.cpf,
        "data_spouse": spouse.issued_date.strftime("%d/%m/%Y"),
        "val_spouse": spouse.expirity.strftime("%d/%m/%Y"),
    }


def build_birth_fields(
    child: CINSchema,
    parents: Sequence[CINSchema],
    *,
    rng: random.Random,
) -> dict[str, str]:
    if len(parents) != 2 or {parent.sex for parent in parents} != {"M", "F"}:
        raise DocumentGenerationError(
            "Birth-certificate mockups require one male and one female parent."
        )
    parents_by_name = {parent.name: parent for parent in parents}
    parent_names = child.filliation.splitlines()
    if (
        len(parent_names) != 2
        or any(name not in parents_by_name for name in parent_names)
        or len(set(parent_names)) != 2
    ):
        raise DocumentGenerationError(
            "Birth-certificate parent names must match the child's filiation."
        )

    father = next(parent for parent in parents if parent.sex == "M")
    mother = next(parent for parent in parents if parent.sex == "F")
    child_city, child_uf = _city_and_state(child.naturality)
    father_city, father_uf = _city_and_state(father.naturality)
    mother_city, mother_uf = _city_and_state(mother.naturality)
    registration_date = child.date_of_birth + timedelta(days=4)
    hour = rng.randrange(24)
    minute = rng.randrange(60)

    return {
        "name_cer": str(child.name).center(40),
        "cpf_cer": child.cpf,
        "matricula_cer": str(_numeric_test_registration(rng)).center(40),
        "data_nas": format_long_date(child.date_of_birth),
        "dia_cer": f"{child.date_of_birth.day:02d}",
        "mes_cer": f"{child.date_of_birth.month:02d}",
        "ano_cer": f"{child.date_of_birth.year:04d}",
        "hor_nas": (
            f"{number_to_portuguese_words(hour)} horas e "
            f"{number_to_portuguese_words(minute)} minutos"
        ),
        "municipio_cer": child_city,
        "uf_cer": child_uf,
        "local_nas": "Hospital Santa Fé",
        "municipio_nas": child_city,
        "uf_nas": child_uf,
        "sexo_nas": "masculino" if child.sex == "M" else "feminino",
        "pai_nome": father.name,
        "muni_pai": father_city,
        "uf_pai": father_uf,
        "avos_pai": " / ".join(father.filliation.splitlines()),
        "mae_nome": mother.name,
        "muni_mae": mother_city,
        "uf_mae": mother_uf,
        "avos_mae": " / ".join(mother.filliation.splitlines()),
        "gemeo": "",
        "data_registro": format_long_date(registration_date),
        "dnv": _numeric_dnv(rng),
        "averbacoes": "nada consta",
        "anotacoes": "nada consta",
    }


def render_family_certificates(
    members: Sequence[CINSchema],
    selection: FamilySelection,
    synthetic_parents: Sequence[CINSchema],
    member_identifiers: Sequence[str],
    *,
    templates_dir: Path,
    coordinates_dir: Path,
    output_dir: Path,
    rng: random.Random,
    today: date,
) -> tuple[Path, ...]:
    expected_members = 1 + selection.relative_count
    if len(members) != expected_members:
        raise DocumentGenerationError(
            "Family member count does not match the selected family."
        )
    expected_synthetic = 1 if selection.children and not selection.spouse else 0
    if len(synthetic_parents) != expected_synthetic:
        raise DocumentGenerationError(
            "Synthetic parent data does not match the selected family."
        )
    if len(member_identifiers) != len(members):
        raise DocumentGenerationError(
            "Family member identifiers do not match the generated family."
        )

    spouse_index = 1 if selection.spouse else None
    child_start = 1 + int(selection.spouse) + selection.parents
    spouse = members[spouse_index] if spouse_index is not None else None
    generated_paths: list[Path] = []
    output_dir = Path(output_dir)

    if spouse is not None:
        fields = build_marriage_fields(members[0], spouse, rng=rng, today=today)
        destination = output_dir / "1_Casamento.png"
        _render_certificate(
            fields,
            destination,
            template_path=Path(templates_dir) / "cer_cas.png",
            coordinates_path=Path(coordinates_dir) / "coordenadas_casa.xml",
            expected_fields=CASA_FIELDS,
            font_size_overrides={},
            document_kind="casa",
        )
        generated_paths.append(destination)

    parent_by_name = {member.name: member for member in members}
    parent_by_name.update(
        {parent.name: parent for parent in synthetic_parents}
    )
    for child_index, child in enumerate(members[child_start:], start=child_start):
        filiation_names = child.filliation.splitlines()
        try:
            parents = tuple(parent_by_name[name] for name in filiation_names)
        except KeyError as exc:
            raise DocumentGenerationError(
                "Birth-certificate parent names must match generated family data."
            ) from exc
        fields = build_birth_fields(child, parents, rng=rng)
        age = _age_on(child.date_of_birth, today)
        filename = (
            f"{_folder_name(child.name)}_{age}_{member_identifiers[child_index]}.png"
        )
        destination = output_dir / filename
        _render_certificate(
            fields,
            destination,
            template_path=Path(templates_dir) / "cer_nas.png",
            coordinates_path=Path(coordinates_dir) / "coordenadas_nasc.xml",
            expected_fields=NASCI_FIELDS,
            font_size_overrides={"matricula_cer": 10},
            document_kind="nasci",
        )
        generated_paths.append(destination)

    return tuple(generated_paths)


def _city_and_state(naturality: str) -> tuple[str, str]:
    city, separator, state = naturality.partition("/")
    if not separator or not city or not state:
        raise DocumentGenerationError(
            "Family naturality must use the format City/UF."
        )
    return city, state


def _load_certificate_coordinates(
    path: Path, expected_fields: set[str]
) -> tuple[tuple[int, int], dict[str, dict[str, int]]]:
    path = Path(path)
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise DocumentGenerationError(
            f"Unable to read certificate coordinate XML from '{path}': {exc}"
        ) from exc
    if root.tag != "annotation":
        raise DocumentGenerationError(
            f"Certificate coordinate XML '{path}' must have an <annotation> root."
        )
    size = root.find("size")
    if size is None:
        raise DocumentGenerationError(
            f"Certificate coordinate XML '{path}' is missing its <size> element."
        )
    image_size: list[int] = []
    for dimension in ("width", "height"):
        value = size.findtext(dimension)
        try:
            parsed = int(value) if value is not None else 0
        except ValueError as exc:
            raise DocumentGenerationError(
                f"Certificate coordinate '{dimension}' in '{path}' must be an integer."
            ) from exc
        if parsed <= 0:
            raise DocumentGenerationError(
                f"Certificate coordinate '{dimension}' in '{path}' must be positive."
            )
        image_size.append(parsed)

    fields: dict[str, dict[str, int]] = {}
    for object_node in root.findall("object"):
        raw_name = object_node.findtext("name")
        if raw_name is None:
            raise DocumentGenerationError(
                f"Unexpected or missing certificate field in '{path}'."
            )
        name = FIELD_ALIASES.get(raw_name, raw_name)
        if name not in expected_fields:
            raise DocumentGenerationError(
                f"Unexpected or missing certificate field '{raw_name}' in '{path}'."
            )
        if name in fields:
            raise DocumentGenerationError(
                f"Duplicate certificate field '{name}' in '{path}'."
            )
        box = object_node.find("bndbox")
        if box is None:
            raise DocumentGenerationError(
                f"Certificate field '{name}' in '{path}' is missing its <bndbox>."
            )
        try:
            xmin, ymin, xmax, ymax = (
                int(box.findtext(key) or "")
                for key in ("xmin", "ymin", "xmax", "ymax")
            )
        except ValueError as exc:
            raise DocumentGenerationError(
                f"Certificate field '{name}' in '{path}' has invalid bounds."
            ) from exc
        if (
            xmin < 0
            or ymin < 0
            or xmax < xmin
            or ymax < ymin
            or xmax >= image_size[0]
            or ymax >= image_size[1]
        ):
            raise DocumentGenerationError(
                f"Certificate field '{name}' in '{path}' has out-of-bounds coordinates."
            )
        fields[name] = {
            "x": xmin,
            "y": ymin,
            "width": xmax - xmin + 1,
            "height": ymax - ymin + 1,
        }

    if set(fields) != expected_fields:
        raise DocumentGenerationError(
            f"Certificate coordinate XML '{path}' is missing fields: "
            f"{sorted(expected_fields - set(fields))}."
        )
    return (image_size[0], image_size[1]), fields


def _calibri_font(size: int) -> ImageFont.FreeTypeFont:
    for font_path in FONT_PATHS:
        try:
            font = ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
        if font.getname()[0].casefold() == "calibri":
            return font
    raise DocumentGenerationError(
        "Calibri is unavailable. Install Calibri or configure its font path."
    )


def _wrapped_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    font: ImageFont.FreeTypeFont,
    *,
    field_name: str,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        if draw.textbbox((0, 0), current, font=font)[2] > width:
            raise DocumentGenerationError(
                f"Text cannot fit certificate field '{field_name}'."
            )
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if draw.textbbox((0, 0), current, font=font)[2] > width:
                    raise DocumentGenerationError(
                        f"Text cannot fit certificate field '{field_name}'."
                    )
        lines.append(current)
    return lines


def _fit_certificate_field(
    draw: ImageDraw.ImageDraw,
    text: str,
    rectangle: Mapping[str, int],
    preferred_size: int,
    *,
    field_name: str,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(preferred_size, 6, -1):
        font = _calibri_font(size)
        padding = max(1, min(3, rectangle["height"] // 10))
        available_width = rectangle["width"] - 2 * padding
        available_height = rectangle["height"] - 2 * padding
        try:
            lines = _wrapped_lines(
                draw,
                text,
                available_width,
                font,
                field_name=field_name,
            )
        except DocumentGenerationError:
            continue
        line_bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_height = max(1, line_bbox[3] - line_bbox[1])
        if line_height * len(lines) <= available_height:
            return font, lines, padding
    raise DocumentGenerationError(
        f"Text cannot fit certificate field '{field_name}' at 5 px or larger."
    )


def _render_certificate(
    values: Mapping[str, str],
    destination: Path,
    *,
    template_path: Path,
    coordinates_path: Path,
    expected_fields: set[str],
    font_size_overrides: Mapping[str, int],
    document_kind: str,
) -> None:
    if set(values) != expected_fields:
        missing = sorted(expected_fields - set(values))
        unexpected = sorted(set(values) - expected_fields)
        raise DocumentGenerationError(
            f"Invalid {document_kind} data fields; missing={missing}, "
            f"unexpected={unexpected}."
        )
    expected_size, fields = _load_certificate_coordinates(
        coordinates_path, expected_fields
    )
    try:
        with Image.open(template_path) as source:
            source.load()
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise DocumentGenerationError(
            f"Unable to open certificate template '{template_path}': {exc}"
        ) from exc

    try:
        if image.size != expected_size:
            raise DocumentGenerationError(
                f"Certificate template '{template_path}' has dimensions "
                f"{image.size}, expected {expected_size}."
            )
        draw = ImageDraw.Draw(image)
        style_color = "#303030" if document_kind == "casa" else "#202020"
        for field_name, rectangle in fields.items():
            text = values[field_name]
            if not text:
                continue
            preferred_size = font_size_overrides.get(field_name, 9)
            if document_kind == "nasci":
                preferred_size += 2
            font, lines, padding = _fit_certificate_field(
                draw,
                text,
                rectangle,
                preferred_size,
                field_name=field_name,
            )
            line_bbox = draw.textbbox((0, 0), "Ag", font=font)
            line_height = max(1, line_bbox[3] - line_bbox[1])
            content_height = line_height * len(lines)
            y = rectangle["y"] + max(
                padding, (rectangle["height"] - content_height) // 2
            )
            for line in lines:
                centered_fields = {
                    "name_cer",
                    "matricula_cer",
                    "cpf_cer",
                    "matricula_casa",
                    "dia_cer",
                    "mes_cer",
                    "ano_cer",
                    "uf_cer",
                    "uf_nas",
                    "dia_casa",
                    "mes_casa",
                    "ano_casa",
                    "num_tit",
                    "data_tit",
                    "val_tit",
                    "num_spouse",
                    "data_spouse",
                    "val_spouse",
                }

                # Dentro do loop `for line in lines:`
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]

                if field_name in centered_fields:
                    x = (
                        rectangle["x"]
                        + padding
                        + (rectangle["width"] - 2 * padding - line_width) // 2
                        - line_bbox[0]
                    )
                else:
                    x = rectangle["x"] + padding

                draw.text(
                    (x, y - line_bbox[1]),
                    line,
                    fill=style_color,
                    font=font,
                )
                y += line_height
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG")
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to save certificate mockup '{destination}': {exc}"
        ) from exc
    finally:
        image.close()
