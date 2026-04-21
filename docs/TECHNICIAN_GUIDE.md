# Technician Guide — IT Ticketing System

---

## Accessing the Technician Portal

Open your browser and navigate to:
```
http://YOUR_SERVER_IP:8000/tech
```

Log in with the credentials provided by your administrator.

---

## Your Dashboard

After login, you will see the **Tickets** tab with all tickets currently assigned to you.

### Ticket List

Each row shows:
- **Ticket ID** — unique reference (format: `TKT-YYYYMMDD-NNNN`)
- **User** — the person who submitted the ticket
- **Category / Sub-category** — type of issue
- **Status** — current state
- **Created** — submission date and time

Use the **search bar** to filter by ticket ID, username, or description. Use the **status dropdown** to filter by status.

---

## Working a Ticket

Click any ticket row to open its detail view.

### Updating Ticket Status

Use the **Status** dropdown to reflect the current state of the ticket:
- **Active** — ticket is open and awaiting work
- **In Progress** — actively being worked on
- **On Hold** — waiting for user response or third-party action
- **Resolved** — issue has been fixed
- **Closed** — ticket is fully closed

Click **Update Status** to save.

### Adding Notes

Scroll to the **Notes** section at the bottom of the ticket detail.

1. Type your note in the text box
2. Click **Add Note**

Notes are internal and visible only to staff members (technicians and admins).

### Viewing Attachments

If an end-user uploaded a file when submitting the ticket, it appears in the **Attachments** section. Click the file name to download.

---

## Notifications

The **bell icon** in the top-right corner shows unread notifications.

You will receive a notification when:
- A ticket is **assigned** to you
- A **note is added** to one of your tickets
- A ticket's **status is changed**

Click the bell to open the notification panel. Click a notification to navigate to the related ticket. Click **Mark all as read** to clear the count.

---

## Changing Your Password

1. Click your username or the settings icon in the top-right
2. Select **Change Password**
3. Enter your current password and your new password (min 8 characters)
4. Click **Save**

---

## Tips

- Refresh the page if the ticket list appears stale — the **Last updated** timestamp in the toolbar shows when data was last fetched
- Use descriptive notes to keep a clear audit trail of your actions
- Mark tickets **Resolved** (not just closed) so users are notified their issue is addressed

---

## Support

If you have trouble accessing the portal, contact your system administrator and check:
- You can reach the server IP on port 8000 from your workstation
- Your account credentials are correct
- The server is running (`http://YOUR_SERVER_IP:8000/health` should return `{"status":"ok"}`)
