import os
import random
import re
import shutil
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.schema import CINSchema

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
DEFAULT_PORTRAIT_DIR = DEFAULT_TEMPLATES_DIR / "3x4_templates"
DEFAULT_COORDINATES_PATH = (
    PROJECT_ROOT
    / "app"
    / "pillow"
    / "field_coordinates_images"
    / "CIN_Front_Model.xml"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_LIST_COORDINATES_DIR = (
    PROJECT_ROOT / "app" / "pillow" / "field_coordinates_images"
)
TEMPLATE_FILES = {
    "front": "CIN_Front_Model.jpg",
    "back": "CIN_Back_Model.jpg",
}
LIST_TEMPLATE_FILES = {"front": "C_front.jpg", "back": "C_back.jpg"}
LIST_COORDINATE_FILES = {"front": "C_front.xml", "back": "C_back.xml"}
LIST_FIELDS = {
    "front": {
        "nome",
        "gg",
        "card_issuer",
        "uf",
        "cpf",
        "date_of_birth",
        "filiation",
        "hab",
        "first_hab_date",
        "c_val",
        "c_num_reg",
    },
    "back": {"arr", "place_of_issue", "issue_date"},
}
LIST_FIELD_ALIASES = {"issu_date": "issue_date"}
LIST_CENTERED_FIELDS = {
    "hab",
    "c_num_reg",
    "c_val",
    "cpf",
    "date_of_birth",
    "first_hab_date",

}

FONT_PATHS = (
    "C:/Windows/Fonts/ariblk.ttf",
    "C:/Windows/Fonts/Arial Black.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Black.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/ariblk.ttf",
    "ariblk.ttf",
)
FACE_STYLES = {
    "front": {"font_size": 26, "color": "#303030"},
    "back": {"font_size": 14, "color": "#404040"},
}
MIN_FONT_SIZE = 6
FACE_FIELDS = {
    "front": {
        "name",
        "cpf",
        "sex",
        "date_of_birth",
        "nationality",
        "naturality",
        "expirity",
    },
    "back": {
        "filliation", 
        "card_issuer", 
        "place_of_issue", 
        "issued_date"
    },
}
COORDINATE_FIELD_ALIASES = {
    "filiation": "filliation",
    "issue_date": "issued_date",
}


class DocumentGenerationError(RuntimeError):
    """Raised when the document images cannot be generated as a complete pair."""


def _load_coordinates(path: Path) -> dict[str, Any]:
    path = Path(path)
    coordinates: dict[str, Any] = {}
    for face, expected_fields in FACE_FIELDS.items():
        xml_path = (
            path
            if face == "front"
            else path.with_name("CIN_Back_Model.xml")
        )
        try:
            root = ElementTree.parse(xml_path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise DocumentGenerationError(
                f"Unable to read coordinate XML from '{xml_path}': {exc}"
            ) from exc

        if root.tag != "annotation":
            raise DocumentGenerationError(
                f"Coordinate XML '{xml_path}' must have an <annotation> root."
            )
        size = root.find("size")
        if size is None:
            raise DocumentGenerationError(
                f"Coordinate XML '{xml_path}' is missing its <size> element."
            )
        image_size = {
            dimension: _xml_integer(size.findtext(dimension), xml_path, dimension)
            for dimension in ("width", "height")
        }
        if any(value <= 0 for value in image_size.values()):
            raise DocumentGenerationError(
                f"Image dimensions in '{xml_path}' must be positive integers."
            )

        fields: dict[str, dict[str, int]] = {}
        portrait_rectangle: dict[str, int] | None = None
        for object_node in root.findall("object"):
            raw_name = object_node.findtext("name")
            if raw_name is None or not raw_name.strip():
                raise DocumentGenerationError(
                    f"Coordinate object in '{xml_path}' is missing its <name>."
                )
            raw_name = raw_name.strip()
            if raw_name == "imagem":
                if face != "front" or portrait_rectangle is not None:
                    raise DocumentGenerationError(
                        f"Unexpected or duplicate image coordinate in '{xml_path}'."
                    )
                bounding_box = object_node.find("bndbox")
                if bounding_box is None:
                    raise DocumentGenerationError(
                        f"Image coordinate in '{xml_path}' is missing its <bndbox>."
                    )
                portrait_rectangle = _xml_bounding_box(
                    bounding_box, xml_path, raw_name, image_size
                )
                continue
            field_name = COORDINATE_FIELD_ALIASES.get(raw_name, raw_name)
            if field_name not in expected_fields:
                raise DocumentGenerationError(
                    f"Unexpected coordinate field '{raw_name}' in '{xml_path}'."
                )
            if field_name in fields:
                raise DocumentGenerationError(
                    f"Duplicate coordinate field '{raw_name}' in '{xml_path}'."
                )

            bounding_box = object_node.find("bndbox")
            if bounding_box is None:
                raise DocumentGenerationError(
                    f"Coordinate field '{raw_name}' in '{xml_path}' is missing "
                    "its <bndbox>."
                )
            fields[field_name] = _xml_bounding_box(
                bounding_box, xml_path, raw_name, image_size
            )

        if set(fields) != expected_fields:
            missing_fields = sorted(expected_fields - set(fields))
            raise DocumentGenerationError(
                f"Coordinate XML '{xml_path}' is missing fields for '{face}': "
                f"{missing_fields}."
            )
        coordinates[face] = {"image_size": image_size, "fields": fields}
        if face == "front":
            if portrait_rectangle is None:
                raise DocumentGenerationError(
                    f"Coordinate XML '{xml_path}' is missing the 'imagem' bounding box."
                )
            coordinates[face]["image"] = portrait_rectangle

    return coordinates


def _xml_bounding_box(
    bounding_box: ElementTree.Element,
    xml_path: Path,
    field_name: str,
    image_size: dict[str, int],
) -> dict[str, int]:
    xmin, ymin, xmax, ymax = (
        _xml_integer(bounding_box.findtext(coordinate), xml_path, field_name)
        for coordinate in ("xmin", "ymin", "xmax", "ymax")
    )
    if xmin < 0 or ymin < 0 or xmax < xmin or ymax < ymin:
        raise DocumentGenerationError(
            f"Bounding box for '{field_name}' in '{xml_path}' has invalid coordinates."
        )
    if xmax >= image_size["width"] or ymax >= image_size["height"]:
        raise DocumentGenerationError(
            f"Bounding box for '{field_name}' in '{xml_path}' exceeds the image bounds."
        )
    return {
        "x": xmin,
        "y": ymin,
        "width": xmax - xmin + 1,
        "height": ymax - ymin + 1,
    }


def _xml_integer(value: str | None, xml_path: Path, field_name: str) -> int:
    if value is None:
        raise DocumentGenerationError(
            f"Coordinate '{field_name}' in '{xml_path}' is missing an integer value."
        )
    try:
        return int(value)
    except ValueError as exc:
        raise DocumentGenerationError(
            f"Coordinate '{field_name}' in '{xml_path}' must be an integer."
        ) from exc


def _select_portrait(sex: str, portrait_dir: Path) -> Path:
    portrait_dir = Path(portrait_dir)
    if not portrait_dir.is_dir():
        raise DocumentGenerationError(
            f"Portrait directory does not exist or is not a directory: '{portrait_dir}'."
        )
    try:
        portraits = [
            path
            for path in portrait_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
            and path.name.upper().startswith(f"{sex}_")
        ]
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to read portrait directory '{portrait_dir}': {exc}"
        ) from exc
    if not portraits:
        raise DocumentGenerationError(
            f"No {sex}-prefixed portrait images were found in '{portrait_dir}'."
        )
    return random.choice(portraits)


def _fit_portrait(portrait: Image.Image, size: tuple[int, int]) -> Image.Image:
    converted = portrait.convert("RGB")
    try:
        return ImageOps.fit(
            converted,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
    finally:
        converted.close()


def select_cin_portrait(
    person: CINSchema,
    *,
    portrait_dir: Path = DEFAULT_PORTRAIT_DIR,
) -> Path:
    """Select the source portrait file used when rendering this person's CIN."""
    if not isinstance(person, CINSchema):
        raise TypeError("person must be a validated CINSchema instance.")
    return _select_portrait(person.sex, Path(portrait_dir))


def _paste_portrait(
    document: Image.Image, portrait_path: Path, rectangle: dict[str, int]
) -> None:
    try:
        with Image.open(portrait_path) as source:
            source.load()
            portrait = _fit_portrait(
                source, (rectangle["width"], rectangle["height"])
            )
    except (OSError, ValueError) as exc:
        raise DocumentGenerationError(
            f"Unable to read portrait image '{portrait_path}': {exc}"
        ) from exc

    try:
        document.paste(portrait, (rectangle["x"], rectangle["y"]))
    finally:
        portrait.close()


def _display_value(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for font_path in FONT_PATHS:
        try:
            font = ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
        if font.getname() == ("Arial", "Black"):
            return font
    raise DocumentGenerationError(
        "Arial Black is unavailable. Install Arial Black or configure its font path."
    )


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont,
    *,
    face: str,
    field_name: str,
) -> tuple[list[str], int]:
    padding = max(2, min(8, height // 10))
    available_width = width - 2 * padding
    available_height = height - 2 * padding
    if available_width <= 0 or available_height <= 0:
        raise DocumentGenerationError(
            "A field rectangle is too small to render text "
            f"(face '{face}', field '{field_name}')."
        )

    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        if draw.textbbox((0, 0), current, font=font)[2] > available_width:
            raise DocumentGenerationError(
                "A word cannot fit inside its mapped field rectangle at the "
                f"required font size (face '{face}', field '{field_name}')."
            )
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= available_width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if draw.textbbox((0, 0), current, font=font)[2] > available_width:
                    raise DocumentGenerationError(
                        "A word cannot fit inside its mapped field rectangle at "
                        f"the required font size (face '{face}', field '{field_name}')."
                    )
        lines.append(current)

    line_bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = max(1, line_bbox[3] - line_bbox[1])
    if line_height * len(lines) > available_height:
        raise DocumentGenerationError(
            "Text cannot fit inside its mapped field rectangle at the required "
            f"font size (face '{face}', field '{field_name}')."
        )
    return lines, padding


def _fit_field(
    draw: ImageDraw.ImageDraw,
    text: str,
    rectangle: dict[str, int],
    *,
    face: str,
    field_name: str,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    preferred_size = FACE_STYLES[face]["font_size"]
    last_error: DocumentGenerationError | None = None
    for size in range(preferred_size, MIN_FONT_SIZE - 1, -1):
        font = _font(size)
        try:
            lines, padding = _wrap_lines(
                draw,
                text,
                rectangle["width"],
                rectangle["height"],
                font,
                face=face,
                field_name=field_name,
            )
        except DocumentGenerationError as exc:
            last_error = exc
            continue
        return font, lines, padding

    if last_error is None:
        raise RuntimeError("The configured preferred font size is below the minimum.")
    raise DocumentGenerationError(
        f"{last_error} Text does not fit even at the minimum font size "
        f"({MIN_FONT_SIZE} px)."
    ) from last_error


def _render_face(
    template_path: Path,
    destination: Path,
    face: str,
    coordinates: dict[str, Any],
    person: CINSchema,
    portrait_path: Path,
) -> None:
    try:
        with Image.open(template_path) as source:
            source.load()
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise DocumentGenerationError(
            f"Unable to open template '{template_path}': {exc}"
        ) from exc

    try:
        expected = coordinates[face]["image_size"]
        if image.size != (expected["width"], expected["height"]):
            raise DocumentGenerationError(
                f"Template '{template_path}' has dimensions {image.size}, expected "
                f"({expected['width']}, {expected['height']})."
            )

        if face == "front":
            _paste_portrait(image, portrait_path, coordinates[face]["image"])

        draw = ImageDraw.Draw(image)
        style = FACE_STYLES[face]
        for field_name, rectangle in coordinates[face]["fields"].items():
            text = _display_value(getattr(person, field_name))
            font, lines, padding = _fit_field(
                draw,
                text,
                rectangle,
                face=face,
                field_name=field_name,
            )
            line_bbox = draw.textbbox((0, 0), "Ag", font=font)
            line_height = max(1, line_bbox[3] - line_bbox[1])
            content_height = line_height * len(lines)
            y = rectangle["y"] + max(
                padding, (rectangle["height"] - content_height) // 2
            )
            for line in lines:
                draw.text(
                    (rectangle["x"] + padding, y - line_bbox[1]),
                    line,
                    fill=style["color"],
                    font=font,
                )
                y += line_height

        try:
            image.save(destination, format="JPEG", quality=95)
        except OSError as exc:
            raise DocumentGenerationError(
                f"Unable to save generated image '{destination}': {exc}"
            ) from exc
    finally:
        image.close()


def create_document_images(
    person: CINSchema,
    *,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    portrait_dir: Path = DEFAULT_PORTRAIT_DIR,
    coordinates_path: Path = DEFAULT_COORDINATES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    identifier: str | None = None,
    portrait_path: Path | None = None,
) -> tuple[Path, Path]:
    if not isinstance(person, CINSchema):
        raise TypeError("person must be a validated CINSchema instance.")

    coordinates = _load_coordinates(Path(coordinates_path))
    portrait_path = (
        select_cin_portrait(person, portrait_dir=portrait_dir)
        if portrait_path is None
        else Path(portrait_path)
    )
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to create output directory '{output_dir}': {exc}"
        ) from exc

    template_paths = {
        face: Path(templates_dir) / filename
        for face, filename in TEMPLATE_FILES.items()
    }
    for path in template_paths.values():
        if not path.is_file():
            raise DocumentGenerationError(f"Required template image is missing: '{path}'.")

    identifier = uuid.uuid4().hex if identifier is None else identifier
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("identifier must be a 32-character lowercase hexadecimal UUID.")
    today = date.today()
    age = today.year - person.date_of_birth.year - (
        (today.month, today.day)
        < (person.date_of_birth.month, person.date_of_birth.day)
    )
    folder_name = _folder_name(person.name)
    final_directory = output_dir / f"{folder_name}_{age}_{identifier}"
    try:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=f".{identifier}_", dir=output_dir)
        )
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to create a staging directory under '{output_dir}': {exc}"
        ) from exc

    try:
        for face in ("front", "back"):
            _render_face(
                template_paths[face],
                staging_directory / f"{face}.jpg",
                face,
                coordinates,
                person,
                portrait_path,
            )
        os.replace(staging_directory, final_directory)
    except Exception as exc:
        try:
            shutil.rmtree(staging_directory)
        except OSError as cleanup_error:
            raise DocumentGenerationError(
                f"Document generation failed ({exc}); staging cleanup also failed "
                f"for '{staging_directory}': {cleanup_error}"
            ) from cleanup_error
        if isinstance(exc, OSError):
            raise DocumentGenerationError(
                f"Unable to publish generated images in '{final_directory}': {exc}"
            ) from exc
        raise

    return final_directory / "front.jpg", final_directory / "back.jpg"


def _folder_name(value: str) -> str:
    folder_name = value.lower()
    folder_name = folder_name[:1].upper() + folder_name[1:]
    folder_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", folder_name).strip(" .")
    if not folder_name:
        raise DocumentGenerationError("Person name cannot form a valid output folder name.")
    return folder_name


def _load_list_coordinates(coordinates_dir: Path) -> dict[str, Any]:
    coordinates: dict[str, Any] = {}
    for face, filename in LIST_COORDINATE_FILES.items():
        xml_path = Path(coordinates_dir) / filename
        try:
            root = ElementTree.parse(xml_path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise DocumentGenerationError(
                f"Unable to read List coordinate XML from '{xml_path}': {exc}"
            ) from exc
        if root.tag != "annotation":
            raise DocumentGenerationError(
                f"List coordinate XML '{xml_path}' must have an <annotation> root."
            )
        size = root.find("size")
        if size is None:
            raise DocumentGenerationError(
                f"List coordinate XML '{xml_path}' is missing its <size> element."
            )
        image_size = {
            dimension: _xml_integer(size.findtext(dimension), xml_path, dimension)
            for dimension in ("width", "height")
        }
        if any(value <= 0 for value in image_size.values()):
            raise DocumentGenerationError(
                f"Image dimensions in '{xml_path}' must be positive integers."
            )

        fields: dict[str, dict[str, int]] = {}
        image_rectangle: dict[str, int] | None = None
        for object_node in root.findall("object"):
            raw_name = object_node.findtext("name")
            if raw_name is None or not raw_name.strip():
                raise DocumentGenerationError(
                    f"Coordinate object in '{xml_path}' is missing its <name>."
                )
            raw_name = raw_name.strip()
            bounding_box = object_node.find("bndbox")
            if bounding_box is None:
                raise DocumentGenerationError(
                    f"Coordinate '{raw_name}' in '{xml_path}' is missing its <bndbox>."
                )
            if raw_name == "image":
                if face != "front" or image_rectangle is not None:
                    raise DocumentGenerationError(
                        f"Unexpected or duplicate image coordinate in '{xml_path}'."
                    )
                image_rectangle = _list_xml_bounding_box(
                    bounding_box, xml_path, raw_name, image_size
                )
                continue

            field_name = LIST_FIELD_ALIASES.get(raw_name, raw_name)
            if field_name not in LIST_FIELDS[face]:
                raise DocumentGenerationError(
                    f"Unexpected List coordinate field '{raw_name}' in '{xml_path}'."
                )
            if field_name in fields:
                raise DocumentGenerationError(
                    f"Duplicate List coordinate field '{raw_name}' in '{xml_path}'."
                )
            fields[field_name] = _list_xml_bounding_box(
                bounding_box, xml_path, raw_name, image_size
            )

        if set(fields) != LIST_FIELDS[face]:
            raise DocumentGenerationError(
                f"List coordinate XML '{xml_path}' is missing fields for '{face}': "
                f"{sorted(LIST_FIELDS[face] - set(fields))}."
            )
        if face == "front" and image_rectangle is None:
            raise DocumentGenerationError(
                f"List coordinate XML '{xml_path}' is missing the 'image' box."
            )
        coordinates[face] = {
            "image_size": image_size,
            "fields": fields,
            "image": image_rectangle,
        }
    return coordinates


def _list_xml_bounding_box(
    bounding_box: ElementTree.Element,
    xml_path: Path,
    field_name: str,
    image_size: dict[str, int],
) -> dict[str, int]:
    xmin, ymin, xmax, ymax = (
        _xml_integer(bounding_box.findtext(coordinate), xml_path, field_name)
        for coordinate in ("xmin", "ymin", "xmax", "ymax")
    )
    if (
        xmin < 1
        or ymin < 1
        or xmax < xmin
        or ymax < ymin
        or xmax > image_size["width"]
        or ymax > image_size["height"]
    ):
        raise DocumentGenerationError(
            f"Bounding box for '{field_name}' in '{xml_path}' has invalid "
            "one-based coordinates."
        )
    return {
        "x": xmin - 1,
        "y": ymin - 1,
        "width": xmax - xmin + 1,
        "height": ymax - ymin + 1,
    }


def _list_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to load required List font '{path}': {exc}"
        ) from exc


def _wrap_list_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    width: int,
    field_name: str,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        if draw.textbbox((0, 0), line, font=font)[2] > width:
            raise DocumentGenerationError(
                f"List text contains a word too wide for field '{field_name}'."
            )
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
                if draw.textbbox((0, 0), line, font=font)[2] > width:
                    raise DocumentGenerationError(
                        f"List text contains a word too wide for field '{field_name}'."
                    )
        lines.append(line)
    return lines

def _render_list_face(
    template_path: Path,
    destination: Path,
    face: str,
    coordinates: dict[str, Any],
    values: dict[str, object],
    portrait_path: Path,
    cour_font_path: Path,
    adelia_font_path: Path,
) -> None:
    try:
        with Image.open(template_path) as source:
            source.load()
            image = source.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise DocumentGenerationError(
            f"Unable to open List template '{template_path}': {exc}"
        ) from exc

    try:
        expected = coordinates[face]["image_size"]
        if image.size != (expected["width"], expected["height"]):
            raise DocumentGenerationError(
                f"List template '{template_path}' has dimensions {image.size}, "
                f"expected ({expected['width']}, {expected['height']})."
            )
        if face == "front":
            _paste_portrait(image, portrait_path, coordinates[face]["image"])

        draw = ImageDraw.Draw(image)
        for field_name, rectangle in coordinates[face]["fields"].items():
            value = values[field_name]
            text = value.strftime("%d/%m/%Y") if isinstance(value, date) else str(value)
            is_arr = face == "back" and field_name == "arr"
            is_centered = field_name in LIST_CENTERED_FIELDS
            if not is_arr:
                text = text.upper()
            if field_name == "filiation":
                text = "\n\n".join(
                    line.strip() for line in text.splitlines() if line.strip()
                )
            padding = 0 if is_arr else 2
            last_error: DocumentGenerationError | None = None
            fitted_layout: tuple[
                ImageFont.FreeTypeFont, list[str], int
            ] | None = None
            font_sizes = (11,) if is_arr else range(11, MIN_FONT_SIZE - 1, -1)
            for font_size in font_sizes:
                font = _list_font(
                    adelia_font_path if is_arr else cour_font_path,
                    font_size,
                )
                try:
                    lines = _wrap_list_text(
                        draw,
                        text,
                        font,
                        rectangle["width"] - 2 * padding,
                        field_name,
                    )
                except DocumentGenerationError as exc:
                    last_error = exc
                    continue
                line_bbox = draw.textbbox((0, 0), "Ag", font=font)
                line_height = max(1, line_bbox[3] - line_bbox[1])
                text_height = line_height * len(lines)
                allowed_height = (
                    rectangle["height"] + 2
                    if is_arr
                    else rectangle["height"] - 2 * padding
                )
                if text_height <= allowed_height:
                    fitted_layout = (font, lines, line_height)
                    break

            if fitted_layout is None:
                if last_error is not None:
                    raise DocumentGenerationError(
                        f"{last_error} Text does not fit even at the minimum font "
                        f"size ({MIN_FONT_SIZE}px)."
                    ) from last_error
                raise DocumentGenerationError(
                    f"List text does not fit its field "
                    f"(face '{face}', field '{field_name}')."
                )

            font, lines, line_height = fitted_layout
            text_height = line_height * len(lines)
            y_offset = (rectangle["height"] - text_height) // 2
            y = rectangle["y"] + (
                y_offset if is_arr or is_centered else max(padding, y_offset)
            )
            for line in lines:
                bounds = draw.textbbox((0, 0), line, font=font)
                x = rectangle["x"] + padding - bounds[0]
                if is_arr or is_centered:
                    line_width = bounds[2] - bounds[0]
                    x = rectangle["x"] + (rectangle["width"] - line_width) / 2 - bounds[0]
                draw.text(
                    (x, y - bounds[1]),
                    line,
                    fill="#101010",
                    font=font,
                )
                y += line_height
        rgb_image = image.convert("RGB")
        try:
            rgb_image.save(destination, format="JPEG", quality=95)
        except OSError as exc:
            raise DocumentGenerationError(
                f"Unable to save List image '{destination}': {exc}"
            ) from exc
        finally:
            rgb_image.close()
    finally:
        image.close()


def create_list_document_images(
    front_fields: dict[str, object],
    back_fields: dict[str, object],
    portrait_path: Path,
    *,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    coordinates_dir: Path = DEFAULT_LIST_COORDINATES_DIR,
    output_dir: Path,
) -> tuple[Path, Path]:
    if set(front_fields) != LIST_FIELDS["front"]:
        raise ValueError("front_fields must contain exactly the configured List fields.")
    if set(back_fields) != LIST_FIELDS["back"]:
        raise ValueError("back_fields must contain exactly the configured List fields.")

    coordinates = _load_list_coordinates(Path(coordinates_dir))
    templates_dir = Path(templates_dir)
    template_paths = {
        face: templates_dir / filename
        for face, filename in LIST_TEMPLATE_FILES.items()
    }
    for path in template_paths.values():
        if not path.is_file():
            raise DocumentGenerationError(
                f"Required List template image is missing: '{path}'."
            )

    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DocumentGenerationError(
            f"Unable to create List output directory '{output_dir}': {exc}"
        ) from exc

    font_directory = PROJECT_ROOT / "app" / "external_font"
    cour_font_path = font_directory / "cour.ttf"
    adelia_font_path = font_directory / "adelia.ttf"
    front_path = output_dir / "C_front.jpg"
    back_path = output_dir / "C_back.jpg"
    try:
        for face, destination, values in (
            ("front", front_path, front_fields),
            ("back", back_path, back_fields),
        ):
            _render_list_face(
                template_paths[face],
                destination,
                face,
                coordinates,
                values,
                Path(portrait_path),
                cour_font_path,
                adelia_font_path,
            )
    except Exception as exc:
        cleanup_errors: list[OSError] = []
        for path in (front_path, back_path):
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            raise DocumentGenerationError(
                f"List image generation failed ({exc}); partial image cleanup "
                f"also failed: {cleanup_errors[0]}"
            ) from cleanup_errors[0]
        raise
    return front_path, back_path