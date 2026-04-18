# Technician Guide — MOM IT Helpdesk v4.0

---

## Accessing the Portal

Open any browser on the network and go to:
```
http://SERVER_IP:8000/tech
```
Your admin will give you the server IP and your login credentials.

> If you are a super-admin, use `/admin` instead — logging in at `/tech` redirects you there automatically.

---

## Logging In

Enter your **username** and **password**, then click **Login**.

- Your session stays active for up to **1 hour of inactivity**
- Closing the browser tab ends the session
- Refreshing the page keeps you logged in
- If you get redirected to the login screen unexpectedly, your session timed out — just log in again

---

## Your Dashboard

You see **only tickets assigned to you**. The three summary cards at the top show your counts by status (Active, In Progress, Resolved).

A blue information banner confirms you are in filtered view. If a ticket is not visible, it has not been assigned to you yet — contact your admin.

---

## Working a Ticket

Click any ticket row to open the detail panel.

**Left panel** shows:
- Full ticket details: user, hostname, IP address, issue category, description
- Attached screenshots or files from the end-user
- Internal notes thread

**Right panel** shows:
- Status update controls

### Updating Status

1. Open the ticket
2. Use the **Status** dropdown — choose Active, In Progress, or Resolved
3. Click **Save Status**

The admin receives a notification immediately. You can only update status on tickets assigned to you — the server enforces this regardless of what the interface shows.

### Adding an Internal Note

Notes are only visible to IT staff. End-users never see them.

1. Scroll to **Internal Notes** in the left panel
2. Type your note (e.g. "Replaced network cable, monitoring for 30 minutes")
3. Click **Add Note**

Your name and timestamp are recorded automatically. The admin receives a notification when you add a note.

### Downloading Attachments

1. Scroll to **Attachments** in the left panel
2. Click **⬇ Download** next to the file
3. The file saves directly to your Downloads folder

**If the download does nothing or shows an error:**
1. Press `Ctrl+Shift+R` to hard refresh the browser (clears cached JavaScript)
2. Log out and log back in
3. Try downloading again

Do not use right-click → Save As on the download button — always click it directly.

---

## Notification Bell 🔔

The bell icon in the top-right corner shows unread notifications. A red badge shows the count.

**You are notified when:**
- A ticket is assigned to you
- A note is added to one of your tickets
- The status of one of your tickets is changed by the admin

**To use notifications:**
1. Click the 🔔 bell — a dropdown opens
2. Click any notification — it marks as read and opens the related ticket
3. Click **Mark all read** to clear all at once

**Green dot** next to the bell = live connection, notifications arrive instantly.
**Grey dot** = fallback mode, notifications update every 30 seconds. No notifications are lost.

---

## Filtering Your Ticket List

Use the filter bar above the table:

| Filter | What it does |
|---|---|
| Status dropdown | Show only Active, In Progress, or Resolved tickets |
| Category dropdown | Show only a specific issue type (e.g. Printer, Email) |
| Show All button | Clears all active filters |

---

## Changing Your Password

1. Click **👤 Account** in the top navigation bar (top-right, next to Logout)
2. Enter your current password
3. Enter and confirm your new password (minimum 8 characters)
4. Click **Change Password**

If you are locked out and cannot log in, contact your admin — they will delete and re-create your account.

---

## Common Questions

**A ticket I should see is not appearing.**
It is not assigned to you yet. Contact your admin.

**Can I reassign this ticket to another technician?**
No. Only admins can assign and reassign tickets.

**I tried to update the status and got a "403" error.**
The ticket was reassigned away from you. Refresh the page — if it disappears from your list, that confirms it. Contact your admin if you still need to work that ticket.

**The notification bell shows a grey dot instead of green.**
Your browser is blocking the WebSocket connection (sometimes happens on corporate networks). Notifications still arrive via polling every 30 seconds — you will not miss anything.

**The dashboard looks wrong or the download button is not working.**
Press `Ctrl+Shift+R` to hard refresh. This clears cached JavaScript and reloads the latest version of the page.

**I closed the browser tab and lost my session.**
This is expected — the session is tied to the browser tab for security. Log in again. Your ticket data is not lost.
