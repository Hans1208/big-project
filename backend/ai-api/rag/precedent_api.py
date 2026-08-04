"""Client for the Korean precedent information API."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LAW_API_BASE_URL = "https://www.law.go.kr/DRF"

Transport = Callable[[str, float], bytes]

VALID_COURT_TYPE_CODES = {
    "400201",
    "400202",
}


class PrecedentApiError(RuntimeError):
    """Raised when the precedent API returns invalid data."""


@dataclass(frozen=True)
class PrecedentSearchPage:
    total_count: int
    page: int
    items: list[dict[str, str]]


def _read_env_value(
    name: str,
    env_path: Path = Path(".env"),
) -> str:
    environment_value = os.getenv(name)

    if environment_value:
        return environment_value.strip()

    if env_path.exists():
        for raw_line in env_path.read_text(
            encoding="utf-8-sig"
        ).splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            key, separator, value = line.partition("=")

            if separator and key.strip() == name:
                return (
                    value.strip()
                    .strip('"')
                    .strip("'")
                )

    raise PrecedentApiError(
        f"{name} is not configured."
    )


def _default_transport(
    url: str,
    timeout: float,
) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "AIVLE-legal-rag/1.0",
        },
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        return response.read()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _normalize_date(value: Any) -> str:
    return "".join(
        character
        for character in _clean_text(value)
        if character.isdigit()
    )


def _parse_positive_int(
    value: Any,
    default: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return parsed if parsed >= 0 else default


def _validate_date(
    value: str | None,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    clean_value = _normalize_date(value)

    if len(clean_value) != 8:
        raise ValueError(
            f"{field_name} must be YYYYMMDD."
        )

    return clean_value


class PrecedentApiClient:
    """Fetch precedent lists and details from the official API."""

    def __init__(
        self,
        oc: str | None = None,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        self._oc = (
            oc.strip()
            if oc is not None
            else _read_env_value("LAW_API_OC")
        )

        if not self._oc:
            raise PrecedentApiError(
                "LAW_API_OC is empty."
            )

        self._timeout = timeout
        self._transport = (
            transport or _default_transport
        )

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "OC": self._oc,
                **params,
            }
        )

        url = (
            f"{LAW_API_BASE_URL}/{endpoint}"
            f"?{query}"
        )

        try:
            raw_body = self._transport(
                url,
                self._timeout,
            )

            payload = json.loads(
                raw_body.decode(
                    "utf-8-sig",
                    errors="strict",
                )
            )
        except Exception as error:
            raise PrecedentApiError(
                "Precedent API request failed."
            ) from error

        if not isinstance(payload, dict):
            raise PrecedentApiError(
                "Precedent API returned an invalid payload."
            )

        return payload

    def search_precedents(
        self,
        query: str = "",
        search_scope: int = 1,
        display: int = 20,
        page: int = 1,
        court_type_code: str | None = None,
        referenced_law: str | None = None,
        decision_date_from: str | None = None,
        decision_date_to: str | None = None,
        data_source_name: str = "\ub300\ubc95\uc6d0",
        sort: str = "ddes",
    ) -> PrecedentSearchPage:
        clean_query = query.strip()
        clean_referenced_law = (
            referenced_law.strip()
            if referenced_law is not None
            else ""
        )

        if not clean_query and not clean_referenced_law:
            raise ValueError(
                "query or referenced_law is required."
            )

        if search_scope not in {1, 2}:
            raise ValueError(
                "search_scope must be 1 or 2."
            )

        if not 1 <= display <= 100:
            raise ValueError(
                "display must be between 1 and 100."
            )

        if page < 1:
            raise ValueError(
                "page must be at least 1."
            )

        if (
            court_type_code is not None
            and court_type_code
            not in VALID_COURT_TYPE_CODES
        ):
            raise ValueError(
                "court_type_code must be "
                "400201 or 400202."
            )

        start_date = _validate_date(
            decision_date_from,
            "decision_date_from",
        )
        end_date = _validate_date(
            decision_date_to,
            "decision_date_to",
        )

        if bool(start_date) != bool(end_date):
            raise ValueError(
                "decision date range requires both dates."
            )

        if (
            start_date is not None
            and end_date is not None
            and start_date > end_date
        ):
            raise ValueError(
                "decision_date_from must not be "
                "after decision_date_to."
            )

        params: dict[str, Any] = {
            "target": "prec",
            "type": "JSON",
            "search": search_scope,
            "display": display,
            "page": page,
            "sort": sort,
        }

        if clean_query:
            params["query"] = clean_query

        if court_type_code is not None:
            params["org"] = court_type_code

        if clean_referenced_law:
            params["JO"] = clean_referenced_law

        if start_date and end_date:
            params["prncYd"] = (
                f"{start_date}~{end_date}"
            )

        clean_data_source = data_source_name.strip()

        if clean_data_source:
            params["datSrcNm"] = clean_data_source

        payload = self._request(
            "lawSearch.do",
            params,
        )

        root = payload.get("PrecSearch")

        if not isinstance(root, dict):
            raise PrecedentApiError(
                "PrecSearch response is missing."
            )

        if root.get("resultMsg") == "fail":
            raise PrecedentApiError(
                _clean_text(
                    root.get(
                        "resultCode",
                        "Precedent search failed.",
                    )
                )
            )

        raw_items = root.get("prec", [])

        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        if raw_items is None:
            raw_items = []

        if not isinstance(raw_items, list):
            raise PrecedentApiError(
                "Precedent search results are invalid."
            )

        items: list[dict[str, str]] = []

        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue

            items.append(
                {
                    "precedent_id": _clean_text(
                        raw_item.get(
                            "\ud310\ub840\uc77c\ub828\ubc88\ud638",
                            raw_item.get("id", ""),
                        )
                    ),
                    "case_name": _clean_text(
                        raw_item.get(
                            "\uc0ac\uac74\uba85",
                            "",
                        )
                    ),
                    "case_number": _clean_text(
                        raw_item.get(
                            "\uc0ac\uac74\ubc88\ud638",
                            "",
                        )
                    ),
                    "decision_date": _normalize_date(
                        raw_item.get(
                            "\uc120\uace0\uc77c\uc790",
                            "",
                        )
                    ),
                    "court_name": _clean_text(
                        raw_item.get(
                            "\ubc95\uc6d0\uba85",
                            "",
                        )
                    ),
                    "court_type_code": _clean_text(
                        raw_item.get(
                            "\ubc95\uc6d0\uc885\ub958\ucf54\ub4dc",
                            "",
                        )
                    ),
                    "case_type_name": _clean_text(
                        raw_item.get(
                            "\uc0ac\uac74\uc885\ub958\uba85",
                            "",
                        )
                    ),
                    "case_type_code": _clean_text(
                        raw_item.get(
                            "\uc0ac\uac74\uc885\ub958\ucf54\ub4dc",
                            "",
                        )
                    ),
                    "decision_type": _clean_text(
                        raw_item.get(
                            "\ud310\uacb0\uc720\ud615",
                            "",
                        )
                    ),
                    "decision": _clean_text(
                        raw_item.get(
                            "\uc120\uace0",
                            "",
                        )
                    ),
                    "data_source_name": _clean_text(
                        raw_item.get(
                            "\ub370\uc774\ud130\ucd9c\ucc98\uba85",
                            "",
                        )
                    ),
                    "detail_link": _clean_text(
                        raw_item.get(
                            "\ud310\ub840\uc0c1\uc138\ub9c1\ud06c",
                            "",
                        )
                    ),
                }
            )

        return PrecedentSearchPage(
            total_count=_parse_positive_int(
                root.get("totalCnt"),
                len(items),
            ),
            page=_parse_positive_int(
                root.get("page"),
                page,
            ),
            items=items,
        )

    def get_precedent(
        self,
        precedent_id: str,
    ) -> dict[str, Any]:
        clean_precedent_id = precedent_id.strip()

        if not clean_precedent_id:
            raise ValueError(
                "precedent_id must not be empty."
            )

        return self._request(
            "lawService.do",
            {
                "target": "prec",
                "type": "JSON",
                "ID": clean_precedent_id,
            },
        )