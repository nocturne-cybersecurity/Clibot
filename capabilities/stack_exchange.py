"""Stack Exchange API integration for searching Stack Overflow and other sites."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote


class StackExchangeIntegration:
    """Stack Exchange API client for searching questions and answers."""

    def __init__(self, key: str | None = None):
        self.key = key or os.environ.get("STACK_EXCHANGE_KEY")
        self.base_url = "https://api.stackexchange.com/2.3"
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _request(self, endpoint: str, params: dict[str, str | int]) -> dict:
        """Make a GET request to Stack Exchange API."""
        url = f"{self.base_url}{endpoint}"
        query_params = {
            "site": params.pop("site", "stackoverflow"),
            "pagesize": min(params.pop("pagesize", 10), 100),
            "filter": "withbody",  # Include body content
        }
        if self.key:
            query_params["key"] = self.key
        query_params.update(params)

        query_string = "&".join(f"{k}={quote(str(v))}" for k, v in query_params.items())
        url += f"?{query_string}"

        try:
            request = Request(url, headers={"User-Agent": "CLIBOT-Terminal-Assistant"})
            with urlopen(request, timeout=10) as response:
                # Update rate limit info from headers
                self.rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                self.rate_limit_reset = response.headers.get("X-RateLimit-Reset")

                result = json.loads(response.read(2_000_000).decode("utf-8"))

                # Check for API errors
                if "error_id" in result:
                    error_message = result.get("error_message", "Unknown error")
                    error_id = result.get("error_id")
                    raise RuntimeError(f"Stack Exchange API error {error_id}: {error_message}")

                return result
        except HTTPError as exc:
            if exc.code == 429:
                raise RuntimeError("Límite de tasa de Stack Exchange excedido. Espera antes de volver a intentar.") from exc
            if exc.code == 400:
                raise RuntimeError("Parámetros inválidos para la API de Stack Exchange.") from exc
            raise RuntimeError(f"Error HTTP {exc.code} de Stack Exchange API.") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"No se pudo conectar con Stack Exchange: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta inválida de Stack Exchange API: {exc}") from exc

    def search_questions(
        self,
        query: str,
        site: str = "stackoverflow",
        tags: list[str] | None = None,
        sort: str = "relevance",
        order: str = "desc",
        pagesize: int = 10,
    ) -> dict:
        """Search for questions on a Stack Exchange site."""
        params = {
            "intitle": query,
            "site": site,
            "sort": sort,
            "order": order,
            "pagesize": pagesize,
        }
        if tags:
            params["tagged"] = ";".join(tags)

        result = self._request("/search/advanced", params)
        return {
            "total": result.get("total", 0),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("body", "")[:500] if item.get("body") else "",
                    "tags": item.get("tags", []),
                    "score": item.get("score"),
                    "answer_count": item.get("answer_count"),
                    "view_count": item.get("view_count"),
                    "creation_date": item.get("creation_date"),
                    "accepted_answer_id": item.get("accepted_answer_id"),
                    "question_id": item.get("question_id"),
                    "owner": item.get("owner", {}).get("display_name") if item.get("owner") else None,
                }
                for item in result.get("items", [])
            ],
        }

    def get_question(self, question_id: int, site: str = "stackoverflow") -> dict:
        """Get detailed information about a specific question."""
        params = {
            "site": site,
            "filter": "withbody",
        }
        result = self._request(f"/questions/{question_id}", params)

        if not result.get("items"):
            return {"error": "Question not found"}

        item = result["items"][0]
        return {
            "title": item.get("title"),
            "url": item.get("link"),
            "body": item.get("body", ""),
            "tags": item.get("tags", []),
            "score": item.get("score"),
            "answer_count": item.get("answer_count"),
            "view_count": item.get("view_count"),
            "creation_date": item.get("creation_date"),
            "accepted_answer_id": item.get("accepted_answer_id"),
            "question_id": item.get("question_id"),
            "owner": item.get("owner", {}).get("display_name") if item.get("owner") else None,
        }

    def get_answers(self, question_id: int, site: str = "stackoverflow") -> dict:
        """Get answers for a specific question."""
        params = {
            "site": site,
            "filter": "withbody",
            "sort": "votes",
            "order": "desc",
        }
        result = self._request(f"/questions/{question_id}/answers", params)

        return {
            "results": [
                {
                    "answer_id": item.get("answer_id"),
                    "body": item.get("body", ""),
                    "score": item.get("score"),
                    "is_accepted": item.get("is_accepted", False),
                    "creation_date": item.get("creation_date"),
                    "owner": item.get("owner", {}).get("display_name") if item.get("owner") else None,
                    "url": f"{item.get('link')}" if item.get("link") else None,
                }
                for item in result.get("items", [])
            ],
        }

    def search_similar(
        self,
        title: str,
        site: str = "stackoverflow",
        pagesize: int = 10,
    ) -> dict:
        """Search for similar questions based on title."""
        params = {
            "title": title,
            "site": site,
            "pagesize": pagesize,
        }
        result = self._request("/similar", params)
        return {
            "total": result.get("total", 0),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "tags": item.get("tags", []),
                    "score": item.get("score"),
                    "answer_count": item.get("answer_count"),
                    "question_id": item.get("question_id"),
                }
                for item in result.get("items", [])
            ],
        }

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status."""
        return {
            "remaining": self.rate_limit_remaining,
            "reset": self.rate_limit_reset,
        }


# Capability functions for registration
_stackexchange_client = None


def _get_client() -> StackExchangeIntegration:
    """Get or create Stack Exchange client instance."""
    global _stackexchange_client
    if _stackexchange_client is None:
        _stackexchange_client = StackExchangeIntegration()
    return _stackexchange_client


def search_questions(
    query: str,
    site: str = "stackoverflow",
    tags: list[str] | None = None,
    pagesize: int = 10,
) -> dict:
    """Search for questions on Stack Exchange."""
    client = _get_client()
    return client.search_questions(query, site, tags, pagesize=pagesize)


def get_question(question_id: int, site: str = "stackoverflow") -> dict:
    """Get detailed question information."""
    client = _get_client()
    return client.get_question(question_id, site)


def get_answers(question_id: int, site: str = "stackoverflow") -> dict:
    """Get answers for a question."""
    client = _get_client()
    return client.get_answers(question_id, site)


def search_similar(title: str, site: str = "stackoverflow", pagesize: int = 10) -> dict:
    """Search for similar questions."""
    client = _get_client()
    return client.search_similar(title, site, pagesize)


def get_rate_limit_status() -> dict:
    """Get Stack Exchange API rate limit status."""
    client = _get_client()
    return client.get_rate_limit_status()
