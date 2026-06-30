> **What rebalance ships (2026-06-04):** Option 2 below — the Gmail API + local
> Desktop OAuth flow — implemented in [scripts/setup_gmail_oauth.py](../../scripts/setup_gmail_oauth.py).
> The token is stored in the OS **keyring** (not a loose `token.json`), with a
> pickle-file fallback for launchd, exactly mirroring the Calendar credential
> model. See README → "Step 5 — Connect Gmail" for the operator steps. This
> note is kept as background on the alternatives.

If you are building a local CLI app and want to read your own Gmail, you have two distinct paths. You can either use the App Password workaround to skip OAuth entirely, or you can use Google's official "Desktop App" OAuth flow, which only requires you to authenticate via a browser once.

### Option 1: IMAP + Google App Password (The "No OAuth" Shortcut)

This is the easiest method if you just want to write a quick script using standard email protocols. It bypasses the OAuth web flow entirely and relies on legacy authentication.

**How it works:** You use standard IMAP to connect to `imap.gmail.com` on port 993. Instead of your real password, you provide a 16-character App Password.

**Setup Steps:**

1. Ensure **2-Step Verification** is enabled on your Google account.
2. Go to your Google Account Security settings and navigate to **App passwords**.
3. Generate a new password, name it after your CLI app, and copy the 16-character string.
4. Use a standard IMAP library in your programming language (like `imaplib` in Python or `imap` in Node.js) with your Gmail address and the App Password to fetch emails.

**The Catch:** This gives your script full, unrestricted read, write, and delete access to your entire mailbox.

---

### Option 2: Gmail API + Local OAuth Flow (The "Proper" Way)

If you want to use the official Gmail API (which is faster and allows for granular permissions, like "Read-Only" access), you *must* use OAuth. However, Google has a specific flow for CLI/Desktop apps so you don't need a public web server.

**How it works:** On the very first run, your CLI app generates an authorization URL. You open it in your local browser, click "Allow," and the browser redirects an auth token back to a temporary local port spun up by your script (e.g., `http://localhost:8080`). The script saves this token locally as a `token.json` file and uses it silently in the background for all future runs.

**Setup Steps:**

1. Go to the **Google Cloud Console**, create a new project, and enable the **Gmail API**.
2. Navigate to Credentials, create an **OAuth client ID**, and specifically select **Desktop app** as the application type.
3. Download the `credentials.json` file directly into your CLI app's directory.
4. Use an official Google Client Library to handle the local auth flow and fetch your mail.

**The Catch:** It requires initial configuration in the Google Cloud Console and requires you to manually click through a browser window on the very first execution.

Which programming language are you writing your CLI app in? I can provide a quick code snippet for either the IMAP or the Gmail API approach to get you up and running.