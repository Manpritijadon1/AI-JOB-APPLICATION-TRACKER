from typing import Any

import httpx


class APIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)

    @property
    def authentication_failed(self) -> bool:
        return self.status_code == 401


class APIClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    headers=headers,
                    json=json,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise APIError(0, "The API request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            raise APIError(
                0,
                "Could not connect to the API. Check that the FastAPI server is running.",
            ) from exc

        if response.is_error:
            raise APIError(
                response.status_code,
                _safe_error_message(response, unauthenticated=token is None),
            )
        if response.status_code == 204:
            return True
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError(
                response.status_code,
                "The API returned an invalid response.",
            ) from exc


def _safe_error_message(
    response: httpx.Response,
    *,
    unauthenticated: bool = False,
) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None

    if response.status_code == 401:
        if unauthenticated and detail == "Incorrect email or password":
            return detail
        if unauthenticated:
            return "Authentication failed. Please check your credentials."
        return "Your session has expired or is invalid. Please sign in again."
    if response.status_code == 422 and isinstance(detail, list):
        errors = []
        for error in detail[:5]:
            if not isinstance(error, dict):
                continue
            location = ".".join(
                str(part) for part in error.get("loc", []) if part != "body"
            )
            message = error.get("msg")
            if isinstance(message, str):
                errors.append(f"{location}: {message}" if location else message)
        if errors:
            return "Please check the form: " + "; ".join(errors)
        return "Please check the submitted fields."
    if isinstance(detail, str) and 400 <= response.status_code < 500:
        return detail[:300]
    if response.status_code == 503:
        return "A required service is unavailable. Check the API or local Ollama service."
    if response.status_code == 504:
        return "The local AI service timed out. Please try again."
    if response.status_code >= 500:
        return "The server could not complete the request. Please try again later."
    return f"The request failed with HTTP {response.status_code}."
