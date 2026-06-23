# Setup — service-account auth for a client

This plugin authenticates to Google with a **service account** (a robot identity
in a Google Cloud project). This guide covers what access you need, how to create
the account, and the two ways to let it reach a client's files.

---

## What level of access do you need from the client?

There are **two privilege tiers**. Pick based on whether the bot must act *as a
user / across the whole org* (domain-wide delegation) or only on *files explicitly
shared with it*.

### Tier 1 — Shared-access model (LOW privilege, recommended default)

The service account only touches files/folders that are explicitly shared with
its email address. Nothing org-wide.

**What to request from the client:**
- A **Google Cloud project** (existing or new) where you can create the service
  account. To do the setup yourself you need, on that project, either the
  **Owner** role, or this minimal set:
  - `roles/iam.serviceAccountAdmin` — create the service account
  - `roles/iam.serviceAccountKeyAdmin` — create its JSON key
  - `roles/serviceusage.serviceUsageAdmin` — enable the Sheets/Docs/Drive APIs
- **No Google Workspace admin rights required.**
- For each Drive folder / Shared Drive the bot should use, the client (or any
  user) just **shares it with the service-account email** (e.g.
  `docs-bot@project-id.iam.gserviceaccount.com`) as Editor.

This is the cleanest ask for a nonprofit client: "Give me a Google Cloud project
I can create a service account in, and share the folder we'll work in with the
service account's email." No one hands you their password or super-admin keys.

> Note: files the service account *creates* are owned by the service account and
> live in its (quota-limited) Drive unless created in — or moved to — a **Shared
> Drive** the account belongs to. For an ongoing client engagement, make a Shared
> Drive, add the service-account email as a Content Manager, and create files
> there (`--parent <sharedDriveFolderId>`).

### Tier 2 — Domain-wide delegation (HIGH privilege)

The service account can **impersonate any user in the Workspace domain** and act
as them (create docs in their personal Drive, etc.). Use this only if the bot
must operate org-wide or as specific named users.

**What to request — in addition to Tier 1:**
- A **Google Workspace Super Admin** must authorize the service account in the
  Admin console: **Admin console → Security → Access and data control → API
  controls → Domain-wide delegation → Add new**, entering the service account's
  **Client ID** and these scopes:
  ```
  https://www.googleapis.com/auth/spreadsheets,
  https://www.googleapis.com/auth/documents,
  https://www.googleapis.com/auth/drive
  ```
- You do **not** need ongoing Super Admin access — just that one-time
  authorization performed by their admin (or temporary Super Admin granted to
  you). Then set `GOOGLE_IMPERSONATE_SUBJECT` to the user to act as.

**Bottom line:** Default to Tier 1 — only a Cloud project + a shared folder, no
admin credentials. Escalate to Tier 2 (one Super-Admin authorization) only if the
client genuinely needs the bot to act as users across the domain.

---

## Step-by-step (Tier 1)

1. **Pick/create a Google Cloud project** (https://console.cloud.google.com).
2. **Enable the APIs** for that project (APIs & Services → Enable APIs):
   Google Sheets API, Google Docs API, Google Drive API.
3. **Create the service account** (IAM & Admin → Service Accounts → Create).
   Name it e.g. `docs-bot`. No project roles are required for Drive/Docs/Sheets
   data access — that comes from file sharing, not IAM.
4. **Create a JSON key** (the service account → Keys → Add key → JSON) and
   download it. Keep it secret.
5. **Share the working folder / Shared Drive** with the service-account email
   (found on the service account page) as **Editor** / **Content Manager**.

## Step-by-step (Tier 2 — add to Tier 1)

6. On the service account, note its **Client ID** (a long number) and enable
   "domain-wide delegation".
7. Have a Workspace **Super Admin** authorize that Client ID with the three
   scopes above (Admin console path in Tier 2).
8. Set `GOOGLE_IMPERSONATE_SUBJECT=user@theirdomain.org`.

---

## Configure the environment

```bash
# Tier 1 (and base for Tier 2)
export GOOGLE_SERVICE_ACCOUNT_KEY="/secure/path/docs-bot.json"   # path or inline JSON

# Tier 2 only — act as this user
export GOOGLE_IMPERSONATE_SUBJECT="staff@client.org"

# Install deps
pip install -r requirements.txt
```

Verify without touching any data:
```bash
python3 skills/google-docs-sheets/scripts/gsheet.py create --title "Test" --dry-run
```
Then a real smoke test (creates a file owned by the service account):
```bash
python3 skills/google-docs-sheets/scripts/gdoc.py create --title "Hello from Claude"
```

## Security notes

- Treat the JSON key like a password. Store it outside the repo; never commit it.
- Prefer Tier 1 + a Shared Drive over domain-wide delegation when you can.
- Rotate keys periodically (IAM → Keys), and delete the key when an engagement
  ends. Revoke domain-wide delegation in the Admin console if it was granted.
- Grant the service account access only to the specific folders/Drives it needs.

## Alternative: OAuth instead of a service account

For a single user who would rather not create a service account, set
`GOOGLE_OAUTH_REFRESH_TOKEN` (with an OAuth client at
`~/.config/gogcli/credentials.json` or `GOOGLE_OAUTH_CREDENTIALS`), or supply a
short-lived `GOOGLE_ACCESS_TOKEN`. The service-account path is recommended for
client/managed deployments because it is headless and needs no per-user consent.
