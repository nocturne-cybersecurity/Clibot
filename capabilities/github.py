"""GitHub API integration for searching repositories, issues, and code."""
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote


def github_token_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "clibot" / "github.json"


def _saved_github_token() -> str | None:
    try:
        value = json.loads(github_token_path().read_text(encoding="utf-8")).get("token")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def configure_github_token(token: str) -> Path:
    token = token.strip()
    if not token or any(char.isspace() for char in token):
        raise ValueError("El token no puede estar vacío ni contener espacios.")
    path = github_token_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".github-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"token": token}, stream)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    global _github_client
    _github_client = GitHubIntegration(token=token)
    return path


def clear_github_token() -> Path:
    path = github_token_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    global _github_client
    _github_client = None
    return path


class GitHubIntegration:
    """GitHub API client with optional authentication."""

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or _saved_github_token()
        self.base_url = "https://api.github.com"
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with optional authentication."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CLIBOT-Terminal-Assistant",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _request(self, endpoint: str, params: dict[str, str] | None = None,
                 headers: dict[str, str] | None = None) -> dict:
        """Make a GET request to GitHub API."""
        url = f"{self.base_url}{endpoint}"
        if params:
            query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url += f"?{query_string}"

        try:
            request = Request(url, headers=headers or self._get_headers())
            with urlopen(request, timeout=10) as response:
                # Update rate limit info from headers
                self.rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                self.rate_limit_reset = response.headers.get("X-RateLimit-Reset")

                return json.loads(response.read(1_000_000).decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 403:
                raise RuntimeError("Límite de tasa de GitHub excedido. Espera antes de volver a intentar.") from exc
            if exc.code == 401:
                raise RuntimeError("Token de GitHub inválido o no proporcionado.") from exc
            if exc.code == 404:
                return {"message": "Not found", "items": []}
            raise RuntimeError(f"Error HTTP {exc.code} de GitHub API.") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"No se pudo conectar con GitHub: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta inválida de GitHub API: {exc}") from exc

    def search_repositories(
        self,
        query: str,
        language: str | None = None,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 10,
    ) -> dict:
        """Search for repositories on GitHub."""
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),
        }
        if language:
            params["q"] += f" language:{language}"

        result = self._request("/search/repositories", params)
        return {
            "total_count": result.get("total_count", 0),
            "results": [
                {
                    "name": item.get("full_name"),
                    "description": item.get("description"),
                    "url": item.get("html_url"),
                    "stars": item.get("stargazers_count"),
                    "language": item.get("language"),
                    "updated_at": item.get("updated_at"),
                    "license": item.get("license", {}).get("name") if item.get("license") else None,
                }
                for item in result.get("items", [])
            ],
        }

    def search_code(self, query: str, per_page: int = 5) -> dict:
        """Search code on GitHub; its code-search API requires authentication."""
        if not self.token:
            raise RuntimeError('La búsqueda de código de GitHub requiere un token en GITHUB_TOKEN.')
        result = self._request(
            "/search/code",
            {"q": query, "per_page": min(max(int(per_page), 1), 10)},
            {**self._get_headers(), "Accept": "application/vnd.github.text-match+json"},
        )
        return {
            "kind": "code_examples",
            "query": query,
            "source": "GitHub",
            "results": [
                {
                    "repository": item.get("repository", {}).get("full_name"),
                    "path": item.get("path"),
                    "url": item.get("html_url"),
                    "code": [match.get("fragment", "")[:2000]
                             for match in item.get("text_matches", []) if match.get("fragment")][:2],
                }
                for item in result.get("items", [])
            ],
        }

    def search_issues(
        self,
        query: str,
        sort: str = "comments",
        order: str = "desc",
        per_page: int = 10,
    ) -> dict:
        """Search for issues and pull requests."""
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),
        }

        result = self._request("/search/issues", params)
        return {
            "total_count": result.get("total_count", 0),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("html_url"),
                    "state": item.get("state"),
                    "comments": item.get("comments"),
                    "created_at": item.get("created_at"),
                    "author": item.get("user", {}).get("login") if item.get("user") else None,
                    "is_pull_request": "pull_request" in item,
                }
                for item in result.get("items", [])
            ],
        }

    def get_repository(self, owner: str, repo: str) -> dict:
        """Get detailed information about a repository."""
        result = self._request(f"/repos/{owner}/{repo}")
        return {
            "name": result.get("full_name"),
            "description": result.get("description"),
            "url": result.get("html_url"),
            "stars": result.get("stargazers_count"),
            "forks": result.get("forks_count"),
            "open_issues": result.get("open_issues_count"),
            "language": result.get("language"),
            "created_at": result.get("created_at"),
            "updated_at": result.get("updated_at"),
            "license": result.get("license", {}).get("name") if result.get("license") else None,
            "topics": result.get("topics", []),
        }

    def get_readme(self, owner: str, repo: str) -> dict:
        """Get the README content of a repository."""
        result = self._request(f"/repos/{owner}/{repo}/readme")
        # README is often base64 encoded
        import base64
        content = result.get("content", "")
        if result.get("encoding") == "base64":
            try:
                content = base64.b64decode(content).decode("utf-8")
            except Exception:
                pass

        return {
            "content": content,
            "url": result.get("html_url"),
        }

    def get_file_content(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        """Get the content of a specific file in a repository."""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        if ref:
            endpoint += f"?ref={ref}"

        result = self._request(endpoint)
        content = result.get("content", "")
        if result.get("encoding") == "base64":
            import base64
            try:
                content = base64.b64decode(content).decode("utf-8")
            except Exception:
                pass

        return {
            "content": content,
            "path": result.get("path"),
            "url": result.get("html_url"),
        }

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status."""
        result = self._request("/rate_limit")
        return {
            "remaining": self.rate_limit_remaining,
            "reset": self.rate_limit_reset,
            "details": result.get("resources", {}),
        }


# Capability functions for registration
_github_client = None


def _get_client() -> GitHubIntegration:
    """Get or create GitHub client instance."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubIntegration()
    return _github_client


def search_repositories(query: str, language: str | None = None, per_page: int = 10) -> dict:
    """Search for GitHub repositories."""
    client = _get_client()
    return client.search_repositories(query, language, per_page=per_page)


def search_code(query: str, per_page: int = 5) -> dict:
    """Search code on GitHub."""
    return _get_client().search_code(query, per_page)


def search_issues(query: str, per_page: int = 10) -> dict:
    """Search for GitHub issues and pull requests."""
    client = _get_client()
    return client.search_issues(query, per_page=per_page)


def get_repository(owner: str, repo: str) -> dict:
    """Get detailed repository information."""
    client = _get_client()
    return client.get_repository(owner, repo)


def get_readme(owner: str, repo: str) -> dict:
    """Get repository README."""
    client = _get_client()
    return client.get_readme(owner, repo)


def get_file_content(owner: str, repo: str, path: str, ref: str | None = None) -> dict:
    """Get file content from repository."""
    client = _get_client()
    return client.get_file_content(owner, repo, path, ref)


def get_rate_limit_status() -> dict:
    """Get GitHub API rate limit status."""
    client = _get_client()
    return client.get_rate_limit_status()
