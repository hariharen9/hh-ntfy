# 🌌 Universal ntfy Automation Command Center

A serverless, 100% cost-free background tracking network running entirely on **GitHub Actions** and **Python**. It monitors public RSS feeds, filters messages according to highly customized criteria, and sends high-priority, deep-linked push notifications directly to your phone's lock screen using **ntfy.sh**.

---

## 🚀 Active Trackers

| Tracker Name | Target Feed | Criteria | State Cache |
| :--- | :--- | :--- | :--- | :--- |
| **r/CrackWatch Denuvo Tracker** | `/r/CrackWatch` RSS | Flair: `"Denuvo release"` | `data/crackwatch_seen.txt` |

---

## 🛠️ Project Architecture Blueprint

```mermaid
graph TD
    A[GitHub Actions Cron Runner] -->|Wake up every 5 mins| B[Python Tracker Script]
    B -->|Fetch RSS Feed| C(Reddit RSS Feed)
    B -->|Check Seen Posts| D[data/State Cache File]
    B -->|Filter Match Detected| E{Alert Trigger?}
    E -->|Yes| F[Send Encrypted Post Request]
    F -->|ntfy.sh Server| G((Your Phone Notification))
    E -->|No| H[Do Nothing]
    B -->|Write back new links| D
    B -->|If changes exist| I[Commit state back to Repo]
    I -->|Git Commit [skip ci]| J[Update State Cache on GitHub]
```

---

## ⚙️ Setup & Deployment Guide

To deploy this Command Center to your personal GitHub account, follow these two quick steps:

### 1. Configure the Vault Secret
Since your repository is public to ensure unlimited free workflow runtime, your personal `ntfy` channel name must remain private.
1. Go to your repository on GitHub.
2. Select **Settings** ➔ **Secrets and variables** ➔ **Actions**.
3. Click **New repository secret**.
4. Configure:
   * **Name**: `NTFY_CW_DENUVO_SECRET_LINK`
   * **Secret**: `hari_haren_alerts_reddit_denuvo` (or the full URL: `https://ntfy.sh/hari_haren_alerts_reddit_denuvo`)
5. Click **Add secret**.

### 2. Enable Repository Write Permissions
For the scheduler to update the local tracking database (`data/crackwatch_seen.txt`), the automation runner requires write permissions.
1. In your repository **Settings**, go to **Actions** ➔ **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Check **Allow GitHub Actions to create and approve pull requests**.
5. Click **Save**.

---

## 📈 Scalability: Adding a New Tracker

The architecture is designed to act as a **Command Center** for all of your notification tracking pipelines. To add a new automation tracker:

### Step A: Write the Tracker Script
Create a new file in `scripts/` (e.g., `scripts/hardware_deals.py`):
* Make it stateless (reads cached files from `data/your_cache.txt`).
* Use `os.environ.get("NTFY_YOUR_NEW_SECRET")` for the target `ntfy` channel.
* Make it prune historical URLs (e.g., keep the last 150 items).

### Step B: Create a New GitHub Workflow
Create a new file in `.github/workflows/` (e.g., `.github/workflows/deals.yml`):
* Duplicate the `.github/workflows/crackwatch.yml` structure.
* Modify the cron schedules to run as frequently as needed (e.g. `*/10 * * * *`).
* Change the run script target to `python scripts/hardware_deals.py`.
* Map the new vault secret to the environment block.
* Point the automated git commit sequence to add `data/your_cache.txt`.

Both workflows will run completely independently, in isolation, at $0.00 cost under your GitHub Actions free tier limits!
