"""Client for the Korean national law information API."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LAW_API_BASE_URL = "https://www.law.go.kr/DRF"

Transport = Callable[[str, float], bytes]


class LawApiError(RuntimeError):
    """Raised when the law API cannot return valid data."""


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

    raise LawApiError(
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


class LawApiClient:
    """Fetch current statutes from the official law API."""

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
            raise LawApiError(
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
            raise LawApiError(
                "Law API request failed."
            ) from error

        if not isinstance(payload, dict):
            raise LawApiError(
                "Law API returned an invalid payload."
            )

        return payload

    def search_current_laws(
        self,
        query: str,
        display: int = 20,
        page: int = 1,
    ) -> list[dict[str, str]]:
        """Search statutes currently in force."""
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "query must not be empty."
            )

        if not 1 <= display <= 100:
            raise ValueError(
                "display must be between 1 and 100."
            )

        if page < 1:
            raise ValueError(
                "page must be at least 1."
            )

        payload = self._request(
            "lawSearch.do",
            {
                "target": "eflaw",
                "type": "JSON",
                "search": 1,
                "query": clean_query,
                "nw": 3,
                "display": display,
                "page": page,
            },
        )

        root = payload.get("LawSearch")

        if not isinstance(root, dict):
            raise LawApiError(
                "LawSearch response is missing."
            )

        if root.get("resultMsg") == "fail":
            raise LawApiError(
                str(
                    root.get(
                        "resultCode",
                        "Law search failed.",
                    )
                )
            )

        laws = root.get("law", [])

        if isinstance(laws, dict):
            laws = [laws]

        if not isinstance(laws, list):
            raise LawApiError(
                "Law search results are invalid."
            )

        normalized: list[dict[str, str]] = []

        for law in laws:
            if not isinstance(law, dict):
                continue

            normalized.append(
                {
                    "law_id": str(
                        law.get(
                            "\ubc95\ub839ID",
                            "",
                        )
                    ),
                    "mst": str(
                        law.get(
                            "\ubc95\ub839\uc77c\ub828\ubc88\ud638",
                            "",
                        )
                    ),
                    "name": str(
                        law.get(
                            "\ubc95\ub839\uba85\ud55c\uae00",
                            "",
                        )
                    ),
                    "effective_date": str(
                        law.get(
                            "\uc2dc\ud589\uc77c\uc790",
                            "",
                        )
                    ),
                    "law_type": str(
                        law.get(
                            "\ubc95\ub839\uad6c\ubd84\uba85",
                            "",
                        )
                    ),
                    "ministry": str(
                        law.get(
                            "\uc18c\uad00\ubd80\ucc98\uba85",
                            "",
                        )
                    ),
                    "detail_link": str(
                        law.get(
                            "\ubc95\ub839\uc0c1\uc138\ub9c1\ud06c",
                            "",
                        )
                    ),
                }
            )

        return normalized

    def get_current_law(
        self,
        law_id: str,
    ) -> dict[str, Any]:
        """Fetch the current full text for one statute."""
        clean_law_id = law_id.strip()

        if not clean_law_id:
            raise ValueError(
                "law_id must not be empty."
            )

        return self._request(
            "lawService.do",
            {
                "target": "eflaw",
                "type": "JSON",
                "ID": clean_law_id,
            },
        )
