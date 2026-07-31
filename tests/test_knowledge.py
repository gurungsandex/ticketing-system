"""Knowledge base: analysis, draft generation (draft-only), approval workflow."""
from conftest import new_ticket


def _seed_resolved_cluster(client, admin_headers, n=3):
    for i in range(n):
        t = new_ticket(client, category="Printer", sub_category="Paper Jam",
                       description="Paper jam in tray 2")
        client.post(f"/tickets/{t['id']}/notes",
                    json={"content": "Cleared the jam and reset the roller"},
                    headers=admin_headers)
        client.patch(f"/tickets/{t['id']}/status",
                     json={"status": "resolved", "resolution_summary": "Cleared jam"},
                     headers=admin_headers)


def test_analysis_surfaces_candidates(client, admin_headers):
    _seed_resolved_cluster(client, admin_headers, n=3)
    a = client.get("/kb/analysis", headers=admin_headers).json()
    assert a["total_tickets"] >= 3
    assert a["resolved_tickets"] >= 3
    clusters = [c["cluster"] for c in a["kb_candidates"]]
    assert "Printer / Paper Jam" in clusters


def test_generated_content_is_draft_only(client, admin_headers):
    _seed_resolved_cluster(client, admin_headers, n=2)
    d = client.post("/kb/generate-draft",
                    json={"cluster": "Printer / Paper Jam"}, headers=admin_headers).json()
    assert d["source"] == "ai_generated"
    assert d["workflow_status"] == "draft"   # never auto-published
    # It does not appear among published articles.
    published = client.get("/kb/articles?status=published", headers=admin_headers).json()
    assert all(art["id"] != d["id"] for art in published)


def test_only_admin_can_approve(client, admin_headers, make_tech):
    _seed_resolved_cluster(client, admin_headers, n=2)
    d = client.post("/kb/generate-draft",
                    json={"cluster": "Printer / Paper Jam"}, headers=admin_headers).json()
    _, tech_headers = make_tech()
    # Technician cannot approve.
    assert client.post(f"/kb/articles/{d['id']}/review",
                       json={"decision": "approved"}, headers=tech_headers).status_code == 403
    # Admin can.
    r = client.post(f"/kb/articles/{d['id']}/review",
                    json={"decision": "approved"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["workflow_status"] == "approved"


def test_editing_approved_article_reverts_to_draft(client, admin_headers):
    a = client.post("/kb/articles",
                    json={"title": "T", "content": "body", "category": "Printer"},
                    headers=admin_headers).json()
    client.post(f"/kb/articles/{a['id']}/review",
                json={"decision": "approved"}, headers=admin_headers)
    updated = client.patch(f"/kb/articles/{a['id']}",
                           json={"content": "edited body"}, headers=admin_headers).json()
    assert updated["workflow_status"] == "draft"
    assert updated["approved_by"] is None
