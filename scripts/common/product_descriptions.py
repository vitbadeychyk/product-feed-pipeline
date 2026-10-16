"""Read and format product descriptions from Supabase by normalized SKU."""
import os
import re
import html
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

def safe_text(value):
    return "" if value is None else str(value).strip()

def normalize_sku(
    value: object,
) -> str:
    """
    Нормалізує SKU для порівняння.

    Наприклад:

        M 4259EBLR-1
        m 4259eblr-1

    будуть вважатися однаковими.

    Пробіли всередині SKU не видаляємо.
    """

    return safe_text(value).casefold()


# ============================================================
# DESCRIPTION FORMATTER
# ============================================================

def format_description(
    value: object,
) -> str:
    """
    Форматує description для Rozetka / PriceCreator.

    - звичайний текст оформлює HTML-абзацами;
    - блок "Характеристики..." виділяє жирним;
    - кожен пункт із символом • перетворює на <ul><li>;
    - екранує спеціальні HTML-символи у вихідному тексті;
    - прибирає зайві порожні рядки.
    """

    text = safe_text(value)

    if not text:
        return ""

    # --------------------------------------------------------
    # Нормалізація переносів
    # --------------------------------------------------------

    text = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    # --------------------------------------------------------
    # Зайві пробіли та табуляції
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # --------------------------------------------------------
    # Перед "Характеристики..." робимо окремий блок
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]*(Характеристики[^:\n]*:)",
        r"\n\n\1\n",
        text,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Кожен • починаємо з нового рядка
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]*•[ \t]*",
        "\n• ",
        text,
    )

    # --------------------------------------------------------
    # Прибираємо зайві переноси перед •
    # --------------------------------------------------------

    text = re.sub(
        r"\n+\s*•",
        "\n•",
        text,
    )

    # --------------------------------------------------------
    # Не більше одного пустого рядка
    # --------------------------------------------------------

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    ).strip()

    # --------------------------------------------------------
    # Формуємо HTML для PriceCreator
    # --------------------------------------------------------

    lines = text.split("\n")

    html_parts: list[str] = []
    paragraph_lines: list[str] = []
    bullet_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines

        paragraph = " ".join(
            line.strip()
            for line in paragraph_lines
            if line.strip()
        )

        if paragraph:
            html_parts.append(
                f"<p>{html.escape(paragraph)}</p>"
            )

        paragraph_lines = []

    def flush_bullets() -> None:
        nonlocal bullet_items

        if bullet_items:
            items_html = "".join(
                f"<li>{html.escape(item)}</li>"
                for item in bullet_items
            )

            html_parts.append(
                f"<ul>{items_html}</ul>"
            )

        bullet_items = []

    for line in lines:
        line = line.strip()

        if not line:
            flush_paragraph()
            flush_bullets()
            continue

        # ----------------------------------------------------
        # Заголовок "Характеристики..."
        # ----------------------------------------------------

        if re.match(
            r"^Характеристики[^:]*:$",
            line,
            flags=re.IGNORECASE,
        ):
            flush_paragraph()
            flush_bullets()

            html_parts.append(
                f"<p><strong>{html.escape(line)}</strong></p>"
            )
            continue

        # ----------------------------------------------------
        # Пункт списку
        # ----------------------------------------------------

        if line.startswith("•"):
            flush_paragraph()

            item = line.lstrip("•").strip()

            if item:
                bullet_items.append(item)

            continue

        # ----------------------------------------------------
        # Звичайний текст
        # ----------------------------------------------------

        flush_bullets()
        paragraph_lines.append(line)

    flush_paragraph()
    flush_bullets()

    return "".join(html_parts)


# ============================================================
# LOAD DESCRIPTIONS FROM SUPABASE
# ============================================================

def load_supabase_descriptions() -> dict[str, str]:
    """
    Завантажує з Supabase:

        products.sku
        products.description

    Повертає:

        normalized_sku -> formatted_description
    """

    if not SUPABASE_URL:

        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_URL"
        )

    if not SUPABASE_KEY:

        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_KEY"
        )

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/products"
    )

    headers = {
        "apikey": SUPABASE_KEY,
    }

    descriptions: dict[str, str] = {}

    page_size = 1000
    offset = 0
    total_rows = 0

    print()
    print(
        "========================================"
    )
    print(
        "Завантаження описів із Supabase"
    )
    print(
        "========================================"
    )

    while True:

        params = {
            "select": "sku,description",
            "order": "sku.asc",
            "limit": str(page_size),
            "offset": str(offset),
        }

        try:

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=60,
            )

            response.raise_for_status()

        except requests.RequestException as exc:

            raise RuntimeError(
                "Помилка підключення до Supabase: "
                f"{exc}"
            ) from exc

        try:

            rows = response.json()

        except ValueError as exc:

            raise RuntimeError(
                "Supabase повернув "
                "некоректну JSON-відповідь"
            ) from exc

        if not isinstance(rows, list):

            raise RuntimeError(
                "Неочікувана відповідь Supabase: "
                f"{rows}"
            )

        if not rows:
            break

        total_rows += len(rows)

        for row in rows:

            if not isinstance(row, dict):
                continue

            sku = normalize_sku(
                row.get("sku")
            )

            description = format_description(
                row.get("description")
            )

            # Немає SKU
            if not sku:
                continue

            # Немає повного description
            if not description:
                continue

            descriptions[sku] = description

        print(
            f"Оброблено рядків Supabase: "
            f"{total_rows}"
        )

        if len(rows) < page_size:
            break

        offset += page_size

    print()
    print(
        f"Товарів з повним description: "
        f"{len(descriptions)}"
    )

    # --------------------------------------------------------
    # SAFETY
    # --------------------------------------------------------

    if not descriptions:

        raise RuntimeError(
            "У Supabase не знайдено жодного товару "
            "з непорожнім description. "
            "Feed will not be overwritten."
        )

    return descriptions


