"""Backend API client for the Streamlit app."""

import os
from typing import Any

import httpx

# In dev, the backend is on 8000
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class APIError(Exception):
    """Raised when the backend returns an error envelope."""

    def __init__(
        self, code: str, message: str, retryable: bool = False, details: Any = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details


class BackendClient:
    """Client for the SiteScout backend."""

    def __init__(self) -> None:
        self.base_url = BACKEND_URL
        self.headers = {
            "X-API-Key": os.getenv("BACKEND_API_KEY", "9CCwCayKUs3ZSQya0LGFNpJ-kk22lGOu"),
            "X-User-Id": "streamlit-local",
        }
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
        )

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        if 200 <= response.status_code < 300:
            return response.json()  # type: ignore[no-any-return]

        try:
            data = response.json()
            if "error" in data:
                err = data["error"]
                raise APIError(
                    code=err.get("code", "INTERNAL"),
                    message=err.get("message", "An unknown error occurred."),
                    retryable=err.get("retryable", False),
                    details=err.get("details"),
                )
        except ValueError:
            pass

        response.raise_for_status()
        return {}

    def get_cities(self) -> dict[str, Any]:
        """Fetch available cities."""
        return self._handle_response(self.client.get("/v1/cities"))

    def get_categories(self) -> dict[str, Any]:
        """Fetch available categories."""
        return self._handle_response(self.client.get("/v1/categories"))

    def create_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Start a new analysis."""
        return self._handle_response(self.client.post("/v1/analyses", json=payload))

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        """Poll the status and fetch recommendations for an analysis."""
        return self._handle_response(self.client.get(f"/v1/analyses/{analysis_id}"))

    def compare(self, analysis_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Compare zones."""
        return self._handle_response(
            self.client.post(f"/v1/analyses/{analysis_id}/compare", json=payload)
        )

    def what_if(self, analysis_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a what-if scenario."""
        return self._handle_response(
            self.client.post(f"/v1/analyses/{analysis_id}/what-if", json=payload)
        )


# Singleton instance
client = BackendClient()
