"""Self-update gating."""


def test_apply_update_disabled_by_default(client, admin_headers):
    r = client.post("/update/apply", headers=admin_headers)
    assert r.status_code == 403, r.text
    assert "ALLOW_SELF_UPDATE" in r.json()["detail"]


def test_check_reports_self_update_disabled(client, admin_headers):
    r = client.get("/update/check", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["self_update_enabled"] is False


def test_apply_update_requires_super_admin(client, make_tech):
    _, tech_headers = make_tech()
    assert client.post("/update/apply", headers=tech_headers).status_code == 403


def test_apply_update_requires_auth(client):
    assert client.post("/update/apply").status_code == 401
