"""Ticket creation, numbering (incl. concurrency), priority, and RBAC."""
from concurrent.futures import ThreadPoolExecutor

from conftest import new_ticket


def test_ticket_ids_are_sequential_and_unique(client):
    ids = [new_ticket(client)["id"] for _ in range(5)]
    assert len(set(ids)) == 5
    assert all(i.startswith("TKT-") for i in ids)
    # Sequence increments.
    seqs = sorted(int(i.split("-")[-1]) for i in ids)
    assert seqs == list(range(seqs[0], seqs[0] + 5))


def test_concurrent_creation_never_duplicates(client):
    """The core requirement: many simultaneous creates yield distinct numbers."""
    n = 40

    def create(_):
        r = client.post("/tickets/", json={
            "client_id": "c", "ip_address": "1.1.1.1",
            "hostname": "h", "category": "Printer",
        })
        return r.json()["id"]

    with ThreadPoolExecutor(max_workers=12) as ex:
        ids = list(ex.map(create, range(n)))

    assert len(ids) == n
    assert len(set(ids)) == n, "duplicate ticket numbers were generated"


def test_invalid_category_rejected(client):
    r = client.post("/tickets/", json={
        "client_id": "c", "ip_address": "1", "hostname": "h",
        "category": "Not A Real Category",
    })
    assert r.status_code == 400


def test_priority_defaults_and_updates(client, admin_headers):
    t = new_ticket(client, priority="urgent")
    assert t["priority"] == "urgent"
    t2 = new_ticket(client)
    assert t2["priority"] == "normal"
    r = client.patch(f"/tickets/{t2['id']}/priority", json={"priority": "high"},
                     headers=admin_headers)
    assert r.status_code == 200 and r.json()["priority"] == "high"


def test_resolution_summary_captured(client, admin_headers):
    t = new_ticket(client)
    r = client.patch(f"/tickets/{t['id']}/status",
                     json={"status": "resolved", "resolution_summary": "Replaced toner"},
                     headers=admin_headers)
    assert r.status_code == 200
    detail = client.get(f"/tickets/{t['id']}", headers=admin_headers).json()
    assert detail["resolution_summary"] == "Replaced toner"
    assert detail["resolved_at"] is not None


def test_technician_only_sees_assigned(client, admin_headers, make_tech):
    tech_name, tech_headers = make_tech()
    t_assigned = new_ticket(client)
    t_other = new_ticket(client)
    client.patch(f"/tickets/{t_assigned['id']}/assign",
                 json={"assigned_to": tech_name}, headers=admin_headers)

    visible = client.get("/tickets/", headers=tech_headers).json()
    ids = {t["id"] for t in visible}
    assert t_assigned["id"] in ids
    assert t_other["id"] not in ids

    # Direct fetch of an unassigned ticket is forbidden.
    assert client.get(f"/tickets/{t_other['id']}", headers=tech_headers).status_code == 403


def test_technician_cannot_assign(client, admin_headers, make_tech):
    tech_name, tech_headers = make_tech()
    t = new_ticket(client)
    r = client.patch(f"/tickets/{t['id']}/assign",
                     json={"assigned_to": tech_name}, headers=tech_headers)
    assert r.status_code == 403


def test_unauthenticated_cannot_list(client):
    assert client.get("/tickets/").status_code in (401, 403)
