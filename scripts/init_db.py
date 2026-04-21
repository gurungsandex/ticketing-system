"""
IT Ticketing System — Database seed script.

Creates the database tables and inserts demo data:
  - 1 super_admin user    (admin / admin123)
  - 1 technician user     (tech1 / tech1pass)
  - 5 sample tickets

Usage:
    cd backend
    python ../scripts/init_db.py

Run this ONCE on a fresh install to create a working demo environment.
CAUTION: Running on an existing database will skip creation of any records
that conflict with unique constraints, but will not delete existing data.
"""
import sys
import os
from pathlib import Path

# Ensure the backend directory is on the path
BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(BACKEND.parent / ".env")

from database import engine, SessionLocal
import models
from auth import hash_password

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # ── Users ─────────────────────────────────────────
    users = [
        {"username": "admin",  "password": "admin123",  "role": "super_admin"},
        {"username": "tech1",  "password": "tech1pass", "role": "technician"},
    ]

    created_users = []
    for u in users:
        existing = db.query(models.AdminUser).filter(
            models.AdminUser.username == u["username"]
        ).first()
        if not existing:
            obj = models.AdminUser(
                username=u["username"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
            created_users.append(u["username"])
            print(f"  [+] Created user: {u['username']} ({u['role']})")
        else:
            print(f"  [=] User already exists: {u['username']} — skipped")

    # ── Sample Tickets ─────────────────────────────────
    from datetime import datetime

    sample_tickets = [
        {
            "id": "TKT-20240101-0001",
            "client_id": "demo-client-001",
            "username": "jsmith",
            "ip_address": "192.168.1.101",
            "hostname": "DESKTOP-JSMITH",
            "category": "Computer / Workstation",
            "sub_category": "Slow Performance",
            "description": "My computer has been running very slowly for the past week. It takes 5+ minutes to boot.",
            "status": "active",
        },
        {
            "id": "TKT-20240101-0002",
            "client_id": "demo-client-002",
            "username": "mjones",
            "ip_address": "192.168.1.102",
            "hostname": "DESKTOP-MJONES",
            "category": "Network / Internet / WiFi",
            "sub_category": "No Internet",
            "description": "Cannot connect to the internet since this morning. WiFi shows connected but pages don't load.",
            "status": "active",
        },
        {
            "id": "TKT-20240101-0003",
            "client_id": "demo-client-003",
            "username": "bwilliams",
            "ip_address": "192.168.1.103",
            "hostname": "DESKTOP-BWILL",
            "category": "Printer",
            "sub_category": "Not Printing",
            "description": "The shared printer on the 2nd floor stopped responding. Print jobs are stuck in queue.",
            "status": "active",
            "assigned_to": "tech1",
        },
        {
            "id": "TKT-20240101-0004",
            "client_id": "demo-client-004",
            "username": "adavis",
            "ip_address": "192.168.1.104",
            "hostname": "LAPTOP-ADAVIS",
            "category": "Email",
            "sub_category": "Cannot Send / Receive",
            "description": "Outlook is not sending or receiving emails. Error: 'Cannot connect to server'.",
            "status": "active",
        },
        {
            "id": "TKT-20240101-0005",
            "client_id": "demo-client-005",
            "username": "rwilson",
            "ip_address": "192.168.1.105",
            "hostname": "DESKTOP-RWILS",
            "category": "Software / Application",
            "sub_category": "App Won't Open",
            "description": "Adobe Acrobat crashes immediately when I try to open it. I need it urgently for a client document.",
            "status": "active",
        },
    ]

    for t in sample_tickets:
        existing = db.query(models.Ticket).filter(models.Ticket.id == t["id"]).first()
        if not existing:
            obj = models.Ticket(
                id=t["id"],
                client_id=t["client_id"],
                username=t.get("username", ""),
                ip_address=t.get("ip_address", ""),
                hostname=t.get("hostname", ""),
                category=t["category"],
                sub_category=t.get("sub_category"),
                description=t["description"],
                status=t.get("status", "active"),
                assigned_to=t.get("assigned_to"),
            )
            db.add(obj)
            db.commit()
            print(f"  [+] Created ticket: {t['id']} — {t['category']}")
        else:
            print(f"  [=] Ticket already exists: {t['id']} — skipped")

    print()
    print("  ✓ Seed complete.")
    print()
    print("  Default credentials:")
    print("    admin  / admin123   (super_admin)")
    print("    tech1  / tech1pass  (technician)")
    print()
    print("  IMPORTANT: Change these passwords immediately after first login.")

finally:
    db.close()
