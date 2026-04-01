# 📄 PubMed Weekly Digest — GLP-1 RA Treatment Patterns

Automatically searches PubMed every Monday for new publications on **GLP-1 receptor agonist treatment patterns**, including adherence, persistence, switching, and discontinuation. Results are filtered to observational studies and meta-analyses only, summarized with AI, and published to a live dashboard.

---

## 🔍 Search Topic

```
((adherence OR persistence OR switch OR discontinue) AND (GLP-1 OR "GLP-1 RA"))
```

**Included study types:** Real-world studies, cohort studies, cross-sectional studies, case-control studies, meta-analyses

**Excluded:** RCTs, narrative reviews, editorials, case reports, letters, computational studies

---

## 🗓 Update Schedule

- **Every Monday at 8:30 AM Houston time (CDT)**
- Covers new publications from the **past 7 days**
- Up to 25 articles fetched per run (before filtering)

> ⚠️ In winter (November–March), the schedule shifts to 8:30 AM CST. To keep Houston time accurate, update the cron in `.github/workflows/daily_digest.yml` from `"30 13 * * 1"` to `"30 14 * * 1"`.

---

## 🌐 Latest Report

👉 **[View the latest digest here](https://luccia7.github.io/PubMed-Daily-Digest-03312026/)**

---

*Powered by NCBI PubMed E-utilities & Anthropic Claude API*
