from fastapi.testclient import TestClient

from app.config import Settings as MediaSettings
from app.main import create_app as create_media_app
from foxden_portal.contracts import ModuleSummary


def test_real_movies_tv_summary_satisfies_portal_contract(tmp_path):
    configured = MediaSettings(
        config=tmp_path / "media-config",
        staging=tmp_path / "staging",
        media=tmp_path / "library",
        token="media-contract-test-token-123456789",
    )
    with TestClient(create_media_app(configured, start_worker=False)) as client:
        summary = ModuleSummary.model_validate(client.get("/api/platform/v1/summary").json())
        assert summary.module_id == "media"
        assert summary.health.status == "healthy"
        assert summary.module_version == "0.4.1"
        assert summary.activity == []
