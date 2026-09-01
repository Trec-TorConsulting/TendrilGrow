"""Format AI feeding schedules into readable mix-order markdown."""

from __future__ import annotations

import re

# Lower rank is added first. Biologicals and pH always come last.
_MIX_RANK: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("armor si", "potassium silicate", "silica")),
    (1, ("calimagic", "cali magic", "cal-mag", "calmag", "ca/mg", "ca-mg")),
    (2, ("floramicro", "flora micro")),
    (3, ("floragro", "flora gro", "flora grow")),
    (4, ("florabloom", "flora bloom")),
    (5, ("koolbloom", "kool bloom")),
    (6, ("floralicious",)),
    (
        10,
        (
            "hydroguard",
            "great white",
            "southern ag",
            "beneficial",
            "bacillus",
            "inoculant",
            "mycorrhiza",
            "microbes",
            "microbe",
        ),
    ),
    (11, ("ph up", "ph down", "ph+", "ph-")),
)

_MIX_FALLBACK: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, ("calcium", "cal mag")),
    (2, ("micro",)),
    (3, ("gro", "grow")),
    (4, ("bloom",)),
)

_PRODUCT_SPLIT = re.compile(r",\s*(?=[A-Za-z][^,:]{0,48}:\s*)")
_LEADING_INDEX = re.compile(r"^\s*\d+\s*[.)\-]\s*")


def compose_feeding_schedule_md(schedule: list[str] | None) -> str:
    """Render a feeding schedule as spaced, mix-ordered markdown.

    Home Assistant markdown cards collapse single newlines, so every block
    uses blank lines and a numbered product list rather than one pipe-delimited
    sentence.
    """
    steps = [str(item).strip() for item in (schedule or []) if str(item).strip()]
    if not steps:
        return "_No feeding schedule generated yet. Run an AI health check._"

    parts = [_format_step(index, raw) for index, raw in enumerate(steps, 1)]
    return "\n\n---\n\n".join(parts)


def _format_step(index: int, raw: str) -> str:
    parsed = _parse_step(raw)
    lines = [f"### {index}. {parsed['phase']}", ""]
    products = _ordered_products(parsed["products"])
    if products:
        lines.append("**Add in this order:**")
        lines.append("")
        for i, product in enumerate(products, 1):
            lines.append(f"{i}. {product}")
        lines.append("")
    if parsed["est_ec"]:
        lines.append(f"- **Est. EC:** {parsed['est_ec']}")
    if parsed["ph"]:
        lines.append(f"- **pH:** {parsed['ph']}")
    if parsed["note"]:
        lines.append(f"- **Note:** {parsed['note']}")
    extra = [item for item in parsed["extra"] if item]
    for item in extra:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip()


def _parse_step(raw: str) -> dict[str, object]:
    cleaned = _LEADING_INDEX.sub("", raw).strip()
    if "|" not in cleaned:
        return {
            "phase": cleaned,
            "products": [],
            "est_ec": "",
            "ph": "",
            "note": "",
            "extra": [],
        }

    chunks = [chunk.strip() for chunk in cleaned.split("|") if chunk.strip()]
    phase = chunks[0] if chunks else cleaned
    products: list[str] = []
    est_ec = ""
    ph = ""
    note = ""
    extra: list[str] = []

    for chunk in chunks[1:]:
        label, _, value = chunk.partition(":")
        field = _field_name(label if value else chunk)
        payload = value.strip() if value else chunk.strip()
        if field == "add_in_order":
            products.extend(_split_products(payload))
        elif field == "est_ec" and not est_ec:
            est_ec = payload
        elif field == "ph" and not ph:
            ph = payload
        elif field == "note" and not note:
            note = payload
        elif ":" in chunk and _looks_like_product_list(chunk):
            products.extend(_split_products(chunk))
        else:
            extra.append(chunk)

    return {
        "phase": phase,
        "products": products,
        "est_ec": est_ec,
        "ph": ph,
        "note": note,
        "extra": extra,
    }


def _field_name(label: str) -> str:
    key = label.strip().lower().rstrip(":")
    key = key.replace(".", "")
    if key.startswith("add in order") or key in {"mix order", "mixing order"}:
        return "add_in_order"
    if key in {"est ec", "estimated ec", "target ec"} or key == "ec":
        return "est_ec"
    if key in {"ph", "target ph"}:
        return "ph"
    if key in {"note", "notes", "key note"}:
        return "note"
    return ""


def _looks_like_product_list(chunk: str) -> bool:
    return bool(_PRODUCT_SPLIT.search(chunk) or chunk.count(":") >= 2)


def _split_products(text: str) -> list[str]:
    payload = text.strip().rstrip(".")
    if not payload:
        return []
    if ";" in payload:
        return [part.strip() for part in payload.split(";") if part.strip()]
    return [part.strip() for part in _PRODUCT_SPLIT.split(payload) if part.strip()]


def _ordered_products(products: list[str]) -> list[str]:
    decorated = [(_mix_rank(item), i, item) for i, item in enumerate(products)]
    decorated.sort()
    return [item for _rank, _i, item in decorated]


def _mix_rank(product: str) -> tuple[int, str]:
    """Return a sort key so nutrients follow GH mixing order."""
    lower = product.lower()
    name, _, _rest = product.partition(":")
    name_key = name.strip().lower() or lower
    for rank, keys in _MIX_RANK:
        if any(key in lower for key in keys):
            return (rank, name_key)
    for rank, keys in _MIX_FALLBACK:
        for key in keys:
            if key == "micro" and ("microbe" in lower or "hydroguard" in lower):
                continue
            if key in {"gro", "grow"} and "hydroguard" in lower:
                continue
            if key in lower:
                return (rank, name_key)
    return (7, name_key)
