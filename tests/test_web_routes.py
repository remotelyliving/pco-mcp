# tests/test_web_routes.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from pco_mcp.main import create_app
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class TestLandingPage:
    def test_landing_returns_html(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Planning Center" in resp.text

    def test_landing_has_get_started_link(self, client) -> None:
        resp = client.get("/")
        assert "Get Started" in resp.text


class TestSetupGuide:
    def test_setup_guide_returns_html(self, client) -> None:
        resp = client.get("/setup-guide")
        assert resp.status_code == 200
        assert "ChatGPT" in resp.text


class TestAuthStart:
    def test_auth_start_redirects_to_pco(self, client) -> None:
        resp = client.get("/auth/start", follow_redirects=False)
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "api.planningcenteronline.com/oauth/authorize" in location

    def test_auth_start_includes_client_id(self, client) -> None:
        resp = client.get("/auth/start", follow_redirects=False)
        location = resp.headers["location"]
        assert "client_id=test-client-id" in location

    def test_auth_start_includes_callback_url(self, client) -> None:
        resp = client.get("/auth/start", follow_redirects=False)
        location = resp.headers["location"]
        assert "pco-mcp.test" in location
        assert "pco-callback" in location

    def test_auth_start_includes_state(self, client) -> None:
        resp = client.get("/auth/start", follow_redirects=False)
        location = resp.headers["location"]
        assert "state=" in location


class TestDashboard:
    def test_dashboard_missing_token_returns_400(self, client) -> None:
        resp = client.get("/dashboard")
        assert resp.status_code == 400

    def test_dashboard_invalid_token_returns_400(self, client) -> None:
        resp = client.get("/dashboard", params={"token": "bogus-token"})
        assert resp.status_code == 400

    def test_dashboard_valid_token_shows_page(self, client) -> None:
        import uuid
        from pco_mcp.oauth.provider import store_dashboard_token

        # Inject a valid dashboard token directly
        test_token = "test-dashboard-token-abc123"
        test_user_id = str(uuid.uuid4())
        store_dashboard_token(test_token, {
            "user_id": test_user_id,
            "org_name": "Sunrise Church",
        })

        resp = client.get("/dashboard", params={"token": test_token})
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Sunrise Church" in resp.text
        assert "/mcp/" in resp.text

    def test_dashboard_token_is_single_use(self, client) -> None:
        import uuid
        from pco_mcp.oauth.provider import store_dashboard_token

        test_token = "test-single-use-token-xyz"
        store_dashboard_token(test_token, {
            "user_id": str(uuid.uuid4()),
            "org_name": "Test Church",
        })

        # First use succeeds
        resp1 = client.get("/dashboard", params={"token": test_token})
        assert resp1.status_code == 200

        # Second use fails
        resp2 = client.get("/dashboard", params={"token": test_token})
        assert resp2.status_code == 400
