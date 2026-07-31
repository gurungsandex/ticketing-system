"""
IT Ticketing System — Database seed script.

Creates the database tables and inserts demo data:
  - 1 super_admin user    (admin / admin123)
  - 1 technician user     (tech  / tech12345)
  - 10 sample tickets across various categories and statuses

Usage:
    cd backend
    python ../scripts/init_db.py

Run this ONCE on a fresh install to create a working demo environment.
CAUTION: Running on an existing database will skip creation of any records
that conflict with unique constraints, but will not delete existing data.
"""
import sys
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
        {"username": "admin", "password": "admin123",  "role": "super_admin"},
        {"username": "tech",  "password": "tech12345", "role": "technician"},
    ]

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
            print(f"  [+] Created user: {u['username']} ({u['role']})")
        else:
            print(f"  [=] User already exists: {u['username']} — skipped")

    # ── Sample Tickets ─────────────────────────────────
    sample_tickets = [
        {
            "id": "TKT-20240101-0001",
            "client_id": "demo-client-001",
            "username": "jsmith",
            "ip_address": "192.168.1.101",
            "hostname": "DESKTOP-JSMITH",
            "category": "Computer / Workstation",
            "sub_category": "Slow Performance",
            "description": "My computer has been running very slowly for the past week. It takes 5+ minutes to boot and applications freeze frequently.",
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
            "description": "Cannot connect to the internet since this morning. WiFi shows connected but web pages do not load.",
            "status": "active",
            "assigned_to": "tech",
        },
        {
            "id": "TKT-20240101-0003",
            "client_id": "demo-client-003",
            "username": "bwilliams",
            "ip_address": "192.168.1.103",
            "hostname": "DESKTOP-BWILL",
            "category": "Printer",
            "sub_category": "Not Printing",
            "description": "The shared printer on the 2nd floor stopped responding. Print jobs are stuck in queue and cannot be cleared.",
            "status": "in_progress",
            "assigned_to": "tech",
        },
        {
            "id": "TKT-20240101-0004",
            "client_id": "demo-client-004",
            "username": "adavis",
            "ip_address": "192.168.1.104",
            "hostname": "LAPTOP-ADAVIS",
            "category": "Email",
            "sub_category": "Cannot Send / Receive",
            "description": "Outlook is not sending or receiving emails. Error message: 'Cannot connect to server'. This has been happening since yesterday.",
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
            "description": "Adobe Acrobat crashes immediately when I try to open it. Needed urgently for end-of-quarter reports.",
            "status": "resolved",
            "assigned_to": "tech",
        },
        {
            "id": "TKT-20240101-0006",
            "client_id": "demo-client-006",
            "username": "kthompson",
            "ip_address": "192.168.1.106",
            "hostname": "LAPTOP-KTHOM",
            "category": "Computer / Workstation",
            "sub_category": "Won't Turn On",
            "description": "Laptop will not power on at all. Tried holding power button, tried different charger. Completely unresponsive.",
            "status": "in_progress",
            "assigned_to": "tech",
        },
        {
            "id": "TKT-20240101-0007",
            "client_id": "demo-client-007",
            "username": "plee",
            "ip_address": "192.168.1.107",
            "hostname": "DESKTOP-PLEE",
            "category": "Password / Account",
            "sub_category": "Locked Out",
            "description": "Locked out of my Windows account after too many failed login attempts. Need password reset.",
            "status": "resolved",
            "assigned_to": "tech",
        },
        {
            "id": "TKT-20240101-0008",
            "client_id": "demo-client-008",
            "username": "cmartinez",
            "ip_address": "192.168.1.108",
            "hostname": "DESKTOP-CMARZ",
            "category": "Network / Internet / WiFi",
            "sub_category": "Slow Connection",
            "description": "Internet connection is extremely slow. File downloads that normally take seconds are taking 10+ minutes.",
            "status": "active",
        },
        {
            "id": "TKT-20240101-0009",
            "client_id": "demo-client-009",
            "username": "tharris",
            "ip_address": "192.168.1.109",
            "hostname": "LAPTOP-THARR",
            "category": "Software / Application",
            "sub_category": "Installation Error",
            "description": "Cannot install required software. Getting error: 'Installation failed: insufficient permissions'. IT policy prevents admin installs.",
            "status": "active",
        },
        {
            "id": "TKT-20240101-0010",
            "client_id": "demo-client-010",
            "username": "lbrown",
            "ip_address": "192.168.1.110",
            "hostname": "DESKTOP-LBROW",
            "category": "Monitor / Display",
            "sub_category": "No Display",
            "description": "Second monitor stopped working after Windows update yesterday. Device Manager shows display adapter error.",
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
            print(f"  [+] Created ticket: {t['id']} — {t['category']} [{t.get('status','active')}]")
        else:
            print(f"  [=] Ticket already exists: {t['id']} — skipped")

    # ── Canned responses (Live Chat one-click templates) ──
    sample_canned = [
        ("Ask for more details", "Thanks for reaching out! Could you share your device hostname and a brief description of when this issue started?"),
        ("Troubleshooting in progress", "I'm looking into this now — I'll follow up shortly with next steps or a resolution."),
        ("Resolved — please confirm", "This should now be resolved on our end. Could you confirm everything is working as expected on your side?"),
        ("Password reset steps", "I've reset your password. Please log out completely and back in using the temporary password — you'll be prompted to set a new one immediately."),
        ("Waiting on user", "Just checking in — are you still experiencing this issue, or has it been resolved? Let us know if you need anything else."),
        ("Escalation notice", "I'm escalating this to our admin team for further investigation. They'll follow up with you directly — thanks for your patience."),
        ("Please try restarting", "Could you try restarting your device and let me know if the issue persists? This resolves a surprising number of cases."),
        ("Remote session request", "Would it be alright if I connected remotely to take a closer look? I'll walk you through granting access when you're ready."),
    ]
    for title, body in sample_canned:
        existing = db.query(models.CannedResponse).filter(
            models.CannedResponse.title == title
        ).first()
        if not existing:
            db.add(models.CannedResponse(
                title=title, body=body, created_by="admin", is_shared=True,
            ))
            db.commit()
            print(f"  [+] Created canned response: {title}")
        else:
            print(f"  [=] Canned response already exists: {title} — skipped")

    print()
    print("  ✓ Seed complete.")
    print()
    print("  Default credentials:")
    print("    admin  / admin123   (super_admin)")
    print("    tech   / tech12345  (technician)")
    print()
    print("  IMPORTANT: Change these passwords immediately after first login.")

finally:
    db.close()
