from pco_mcp.errors import map_pco_error


def test_401_returns_session_expired() -> None:
    msg = map_pco_error(401, base_url="https://pco-mcp.example.com")
    assert "expired" in msg.lower()
    assert "https://pco-mcp.example.com" in msg


def test_403_returns_permission_message() -> None:
    msg = map_pco_error(403, base_url="https://pco-mcp.example.com")
    assert "permission" in msg.lower()


def test_404_returns_not_found() -> None:
    msg = map_pco_error(404, base_url="https://pco-mcp.example.com")
    assert "found" in msg.lower()


def test_429_returns_rate_limit() -> None:
    msg = map_pco_error(429, base_url="https://pco-mcp.example.com")
    assert "wait" in msg.lower() or "rate" in msg.lower()


def test_500_returns_server_error() -> None:
    msg = map_pco_error(500, base_url="https://pco-mcp.example.com")
    assert "unavailable" in msg.lower() or "try again" in msg.lower()


def test_502_returns_server_error() -> None:
    msg = map_pco_error(502, base_url="https://pco-mcp.example.com")
    assert "unavailable" in msg.lower() or "try again" in msg.lower()


def test_unknown_status_returns_generic() -> None:
    msg = map_pco_error(418, base_url="https://pco-mcp.example.com")
    assert "unexpected" in msg.lower() or "error" in msg.lower()
