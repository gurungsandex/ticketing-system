"""
Query-count behaviour of the ticket list.

The dashboards poll GET /tickets/ every 20-30s per open tab, so the number of
SQL round-trips per request must not grow with the number of tickets.
"""

import pytest
from conftest import new_ticket
from sqlalchemy import event


@pytest.fixture()
def count_queries():
    """Count SQL statements issued while the block runs."""
    import database

    statements = []

    def _before(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    class _Counter:
        def __enter__(self):
            statements.clear()
            event.listen(database.engine, "before_cursor_execute", _before)
            return statements

        def __exit__(self, *exc):
            event.remove(database.engine, "before_cursor_execute", _before)
            return False

    return _Counter


def _add_notes(client, headers, ticket_id, n):
    for i in range(n):
        r = client.post(f"/tickets/{ticket_id}/notes",
                        json={"content": f"note {i}"}, headers=headers)
        assert r.status_code == 200, r.text


def test_listing_query_count_does_not_grow_with_ticket_count(client, admin_headers, count_queries):
    for _ in range(3):
        new_ticket(client)
    with count_queries() as small:
        assert client.get("/tickets/", headers=admin_headers).status_code == 200
    baseline = len(small)

    for _ in range(12):
        new_ticket(client)
    with count_queries() as large:
        r = client.get("/tickets/", headers=admin_headers)
        assert r.status_code == 200
    assert len(r.json()) == 15

    # 5x the tickets must not mean ~5x the queries.
    assert len(large) <= baseline + 2, (
        f"query count scaled with row count: {baseline} queries for 3 tickets, "
        f"{len(large)} for 15 -- N+1 regression"
    )


def test_notes_count_is_still_correct(client, admin_headers):
    """The optimisation must not change what the endpoint reports."""
    a = new_ticket(client, category="Printer")
    b = new_ticket(client, category="Email")
    c = new_ticket(client, category="VPN / Remote Access")
    _add_notes(client, admin_headers, a["id"], 3)
    _add_notes(client, admin_headers, b["id"], 1)

    rows = {t["id"]: t for t in client.get("/tickets/", headers=admin_headers).json()}
    assert rows[a["id"]]["notes_count"] == 3
    assert rows[b["id"]]["notes_count"] == 1
    assert rows[c["id"]]["notes_count"] == 0


def test_single_ticket_notes_count_is_correct(client, admin_headers):
    t = new_ticket(client)
    _add_notes(client, admin_headers, t["id"], 2)
    r = client.get(f"/tickets/{t['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["notes_count"] == 2
