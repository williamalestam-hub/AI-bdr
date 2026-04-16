"""
Single entry point for obtaining HubSpot, Clay, and LLM clients.

Reads BDR_MODE env var:
  - "mock" (default) → always return the mocks
  - "real"           → return real clients; requires API keys
  - unset / other    → "hybrid": return real client if the relevant key is set,
                       otherwise fall back to the mock

Each service is resolved independently so you can wire them up one at a time
(e.g. real ANTHROPIC_API_KEY but still mock HubSpot + Clay).
"""

import os


def _mode() -> str:
    return (os.getenv("BDR_MODE") or "mock").lower()


def _should_use_real(env_key: str) -> bool:
    mode = _mode()
    if mode == "mock":
        return False
    if mode == "real":
        return True
    # hybrid
    return bool(os.getenv(env_key))


def get_hubspot_client():
    if _should_use_real("HUBSPOT_ACCESS_TOKEN"):
        from src.tools.hubspot_client import HubSpotClient
        return HubSpotClient()
    from src.sandbox.mock_hubspot import MockHubSpotClient
    return MockHubSpotClient()


def get_clay_client():
    if _should_use_real("CLAY_API_KEY"):
        from src.tools.clay_client import ClayClient
        return ClayClient()
    from src.sandbox.mock_clay import MockClayClient
    return MockClayClient()


def get_llm():
    """
    Returns either:
      - an anthropic.Anthropic client (real)
      - a MockLLM instance (template-mode)

    The caller inspects .is_mock to decide which code path to take.
    """
    if _should_use_real("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        client.is_mock = False  # type: ignore[attr-defined]
        return client
    from src.sandbox.mock_anthropic import MockLLM
    return MockLLM()


def describe_mode() -> dict:
    """Diagnostic: what will each client resolve to right now?"""
    return {
        "BDR_MODE": _mode(),
        "hubspot": "real" if _should_use_real("HUBSPOT_ACCESS_TOKEN") else "mock",
        "clay": "real" if _should_use_real("CLAY_API_KEY") else "mock",
        "llm": "real" if _should_use_real("ANTHROPIC_API_KEY") else "mock",
    }
