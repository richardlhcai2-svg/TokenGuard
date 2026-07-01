import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestAlertRoutes:
    """Test alert API route registration via OpenAPI schema."""

    def test_openapi_includes_alerts(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]

        assert "/api/v1/alerts/" in paths
        assert "get" in paths["/api/v1/alerts/"]       # list
        assert "post" in paths["/api/v1/alerts/"]      # create

        assert "/api/v1/alerts/{rule_id}" in paths
        assert "patch" in paths["/api/v1/alerts/{rule_id}"]  # update
        assert "delete" in paths["/api/v1/alerts/{rule_id}"] # delete

        assert "/api/v1/alerts/check-now" in paths
        assert "post" in paths["/api/v1/alerts/check-now"]
