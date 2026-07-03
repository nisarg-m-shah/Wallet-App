# Wallet Tracker

A personal finance tracker (Streamlit + SQLAlchemy + Plotly), built for fast entry
and multi-user, publicly-deployable use.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

With no secrets configured, it automatically uses a local SQLite file at `data/finance_tracker.db`.

---

## Deploy globally on Streamlit Community Cloud

Streamlit Community Cloud's filesystem is **ephemeral** - anything written to local
disk (a SQLite file, in our case) is wiped every time the app reboots or redeploys.
So for a public deployment, the app needs a real hosted database. It's already wired
to use Postgres automatically the moment you provide a connection string - no code
changes required.

### Step 1 - Create a free Postgres database

Either works well and both have a generous free tier:

- **Supabase**: [supabase.com](https://supabase.com) -> New project -> Project Settings -> Database
  -> copy the **Connection string (URI)**, "Session pooler" variant.
- **Neon**: [neon.tech](https://neon.tech) -> New project -> copy the connection string from the dashboard.

It'll look like:
```
postgresql://username:password@host:5432/dbname
```

### Step 2 - Push this project to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/wallet-tracker.git
git push -u origin main
```

`.gitignore` already excludes `.streamlit/secrets.toml` and the local SQLite file,
so no credentials or personal data get pushed.

### Step 3 - Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **New app**, pick your repo/branch, and set the main file to `app.py`.
3. Before (or after) deploying, open **Advanced settings -> Secrets** and paste:
   ```toml
   DATABASE_URL = "postgresql://username:password@host:5432/dbname"
   ```
4. Click **Deploy**. On first load the app will create all tables automatically
   (`init_db()` runs on every startup and is safe to re-run).

Your app will be live at `https://<your-app-name>.streamlit.app` - share that
URL with anyone; each person who signs up gets their own isolated accounts,
transactions, and balances.

### Updating the live app

Just push to `main` - Streamlit Community Cloud auto-redeploys on every push.
Since data now lives in Postgres (not the app's filesystem), your transactions
and accounts persist across redeploys and reboots.

---

## Notes on security for a public deployment

- Passwords are bcrypt-hashed, never stored in plain text.
- Every table is scoped by `user_id`; there's no cross-user data access path.
- The free Community Cloud tier does not support custom rate-limiting at the
  infra level - if you want extra protection against brute-force login attempts,
  consider adding a simple attempt counter/lockout in `auth.py` or fronting the
  app with Cloudflare.
- Consider rotating the Postgres password periodically since it lives in
  Streamlit's Secrets manager (encrypted at rest, but still a shared secret).
