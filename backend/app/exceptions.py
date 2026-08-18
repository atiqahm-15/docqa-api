class ProviderUnavailableError(Exception):
    """Raised when the configured LLM provider (Gemini) cannot serve a request."""

    def __init__(self, provider: str, detail: str):
        self.provider = provider
        self.detail = detail
        super().__init__(f"{provider} is unavailable: {detail}")
