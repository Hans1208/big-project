"""Convert law API payloads into article documents."""

from __future__ import annotations

from typing import Any


class StatuteParseError(ValueError):
    """Raised when a statute payload has an invalid shape."""


CONTENT_KEYS: tuple[str, ...] = (
    "\uc870\ubb38\ub0b4\uc6a9",
    "\ud56d\ub0b4\uc6a9",
    "\ud638\ub0b4\uc6a9",
    "\ubaa9\ub0b4\uc6a9",
)

NESTED_UNIT_KEYS: tuple[str, ...] = (
    "\ud56d",
    "\ud56d\ub2e8\uc704",
    "\ud638",
    "\ud638\ub2e8\uc704",
    "\ubaa9",
    "\ubaa9\ub2e8\uc704",
)


def _as_list(
    value: Any,
) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _text_value(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return str(
            value.get("content", "")
        ).strip()

    return str(value).strip()


def _clean_number(
    value: Any,
) -> str:
    text = _text_value(value)

    if not text:
        return ""

    if text.isdigit():
        return str(int(text))

    return text


def _collect_content(
    value: Any,
    output: list[str],
) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_content(
                item,
                output,
            )

        return

    if not isinstance(value, dict):
        return

    for key in CONTENT_KEYS:
        text = _text_value(
            value.get(key)
        )

        if text:
            output.append(text)

    for key in NESTED_UNIT_KEYS:
        if key in value:
            _collect_content(
                value[key],
                output,
            )


def _deduplicate_text(
    values: list[str],
) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean_value = value.strip()

        if not clean_value:
            continue

        normalized = " ".join(
            clean_value.split()
        )

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_values.append(clean_value)

    return unique_values


def _article_label(
    article_number: str,
    branch_number: str,
) -> str:
    if branch_number and branch_number != "0":
        return (
            f"\uc81c{article_number}"
            f"\uc870\uc758{branch_number}"
        )

    return f"\uc81c{article_number}\uc870"


def parse_statute_payload(
    payload: dict[str, Any],
    *,
    mst: str = "",
) -> list[dict[str, str]]:
    """Create one normalized document per statute article."""
    law = payload.get("\ubc95\ub839")

    if not isinstance(law, dict):
        raise StatuteParseError(
            "Statute payload is missing the law root."
        )

    basic = law.get("\uae30\ubcf8\uc815\ubcf4")

    if not isinstance(basic, dict):
        raise StatuteParseError(
            "Statute basic information is missing."
        )

    law_id = _text_value(
        basic.get("\ubc95\ub839ID")
    )
    law_name = _text_value(
        basic.get("\ubc95\ub839\uba85_\ud55c\uae00")
    )

    if not law_id or not law_name:
        raise StatuteParseError(
            "Statute ID or name is missing."
        )

    law_type = _text_value(
        basic.get("\ubc95\uc885\uad6c\ubd84")
    )
    ministry = _text_value(
        basic.get("\uc18c\uad00\ubd80\ucc98")
    )
    effective_date = _text_value(
        basic.get("\uc2dc\ud589\uc77c\uc790")
    )
    promulgation_date = _text_value(
        basic.get("\uacf5\ud3ec\uc77c\uc790")
    )
    promulgation_number = _text_value(
        basic.get("\uacf5\ud3ec\ubc88\ud638")
    )
    law_key = _text_value(
        law.get("\ubc95\ub839\ud0a4")
    )

    article_container = law.get("\uc870\ubb38")

    if not isinstance(article_container, dict):
        return []

    article_units = _as_list(
        article_container.get(
            "\uc870\ubb38\ub2e8\uc704"
        )
    )

    documents: list[dict[str, str]] = []

    for article in article_units:
        if not isinstance(article, dict):
            continue

        article_flag = _text_value(
            article.get("\uc870\ubb38\uc5ec\ubd80")
        )

        if (
            article_flag
            and article_flag != "\uc870\ubb38"
        ):
            continue

        article_number = _clean_number(
            article.get("\uc870\ubb38\ubc88\ud638")
        )
        branch_number = _clean_number(
            article.get(
                "\uc870\ubb38\uac00\uc9c0\ubc88\ud638"
            )
        )

        if not article_number:
            continue

        article_title = _text_value(
            article.get("\uc870\ubb38\uc81c\ubaa9")
        )
        article_label = _article_label(
            article_number,
            branch_number,
        )

        content_parts: list[str] = []

        _collect_content(
            article,
            content_parts,
        )

        content_parts = _deduplicate_text(
            content_parts
        )

        if not content_parts:
            continue

        heading = article_label

        if article_title:
            heading += f"({article_title})"

        text_parts = [
            f"{law_name} {heading}",
            *content_parts,
        ]

        document_id = (
            f"statute:{law_id}:"
            f"{article_number}:"
            f"{branch_number or '0'}"
        )

        documents.append(
            {
                "document_id": document_id,
                "law_id": law_id,
                "mst": mst.strip(),
                "law_key": law_key,
                "law_name": law_name,
                "law_type": law_type,
                "ministry": ministry,
                "effective_date": effective_date,
                "promulgation_date": (
                    promulgation_date
                ),
                "promulgation_number": (
                    promulgation_number
                ),
                "article_key": _text_value(
                    article.get("\uc870\ubb38\ud0a4")
                ),
                "article_number": article_number,
                "article_branch_number": (
                    branch_number
                ),
                "article_label": article_label,
                "article_title": article_title,
                "article_effective_date": (
                    _text_value(
                        article.get(
                            "\uc870\ubb38"
                            "\uc2dc\ud589\uc77c\uc790"
                        )
                    )
                ),
                "text": "\n".join(text_parts),
                "source": f"law_api:{law_id}",
            }
        )

    return documents
