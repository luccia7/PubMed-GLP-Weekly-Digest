# 📄 PubMed Daily Digest

Automatically fetches new PubMed publications on your chosen topics every day, summarizes them with Claude AI, and publishes a dashboard to GitHub Pages — for free.

---

## 🗂 Project Structure

```
pubmed-digest/
├── .github/workflows/
│   └── daily_digest.yml       # GitHub Actions schedule
├── scripts/
│   └── fetch_and_digest.py    # Main script
├── docs/
│   ├── index.html             # Your live dashboard (auto-updated)
│   └── data/                  # JSON history files (auto-generated)
└── README.md
```

---

## 🚀 Setup (5 steps)

### 1. Create a GitHub repository

- Go to [github.com](https://github.com) and create a **new repository** (e.g. `pubmed-digest`)
- Make it **public** (required for free GitHub Pages)
- Push all files from this project into it

### 2. Add your Anthropic API key as a secret

- In your repo → **Settings → Secrets and variables → Actions**
- Click **New repository secret**
- Name: `ANTHROPIC_API_KEY`
- Value: your key from [console.anthropic.com](https://console.anthropic.com)

*(Optional) Add `NCBI_API_KEY` the same way for higher PubMed rate limits — get one free at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/)*

### 3. Configure your topics

Open `scripts/fetch_and_digest.py` and edit the `TOPICS` list:

```python
TOPICS = [
    "CRISPR gene editing",
    "machine learning radiology",
    "Alzheimer's disease biomarkers",
    # Add as many as you want — use standard PubMed search syntax
]
```

You can use full PubMed query syntax, e.g.:
- `"COVID-19 long covid"` — simple keyword
- `"breast cancer[MeSH] AND immunotherapy"` — MeSH terms
- `"nature[journal] AND genomics"` — filter by journal

### 4. Enable GitHub Pages

- In your repo → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / folder: `/docs`
- Click **Save**

Your dashboard will be live at:
`https://<your-username>.github.io/<repo-name>/`

### 5. Trigger your first digest

- Go to **Actions → PubMed Daily Digest → Run workflow**
- Click the green **Run workflow** button
- After ~1 minute, visit your GitHub Pages URL to see the digest!

---

## ⚙️ Customization

| Setting | Location | Default |
|---|---|---|
| Topics | `TOPICS` list in script | 1 placeholder |
| Articles per topic | `MAX_RESULTS_PER_TOPIC` | 5 |
| Days back to search | `DAYS_BACK` | 1 |
| Run time (UTC) | `cron` in workflow file | 7:00 AM |

---

## 🕐 Schedule

The digest runs daily at **7:00 AM UTC** by default. To change this, edit the cron expression in `.github/workflows/daily_digest.yml`:

```yaml
- cron: "0 7 * * *"   # 7 AM UTC daily
```

Use [crontab.guru](https://crontab.guru) to generate custom schedules.

---

## 💰 Cost

- **GitHub Actions**: Free (2,000 min/month on free tier — this uses ~1 min/day)
- **GitHub Pages**: Free
- **NCBI PubMed API**: Free
- **Anthropic Claude API**: Small cost per run (~$0.01–0.05/day depending on topics and article count)
