#!/usr/bin/env python3
"""
PubMed Daily Digest Generator
Fetches new PubMed articles for configured topics and generates AI summaries via Claude API.
"""

import os
import json
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# ─────────────────────────────────────────────
# CONFIGURATION — Edit this section to customize
# ─────────────────────────────────────────────
TOPICS = [
    # Add your PubMed search queries here. These follow standard PubMed syntax.
    # Examples:
    # "CRISPR gene editing",
    # "machine learning radiology",
    # "Alzheimer's disease biomarkers",
    # "mRNA vaccine immunogenicity",
    "large language models medicine",   # placeholder — replace with your topics
]

MAX_RESULTS_PER_TOPIC = 5   # Number of articles to fetch per topic
DAYS_BACK = 1               # How many days back to look for new articles
# ─────────────────────────────────────────────


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")  # Optional but increases rate limits


def build_date_filter(days_back: int) -> str:
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days_back)
    return f"{start.strftime('%Y/%m/%d')}:{today.strftime('%Y/%m/%d')}[dp]"


def search_pubmed(topic: str, days_back: int, max_results: int) -> list[str]:
    """Search PubMed and return a list of PMIDs."""
    date_filter = build_date_filter(days_back)
    query = f"({topic}) AND {date_filter}"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "date",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_article_details(pmids: list[str]) -> list[dict]:
    """Fetch article metadata for a list of PMIDs."""
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        try:
            pmid = article.findtext(".//PMID", "")
            title = article.findtext(".//ArticleTitle", "No title")
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(p.text or "" for p in abstract_parts if p.text).strip()
            if not abstract:
                abstract = "No abstract available."

            authors_els = article.findall(".//Author")
            authors = []
            for a in authors_els[:3]:
                last = a.findtext("LastName", "")
                fore = a.findtext("ForeName", "")
                if last:
                    authors.append(f"{fore} {last}".strip())
            if len(authors_els) > 3:
                authors.append("et al.")

            journal = article.findtext(".//Journal/Title", "") or article.findtext(".//ISOAbbreviation", "")
            pub_date_el = article.find(".//PubDate")
            year = pub_date_el.findtext("Year", "") if pub_date_el is not None else ""
            month = pub_date_el.findtext("Month", "") if pub_date_el is not None else ""

            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "pub_date": f"{month} {year}".strip(),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception as e:
            print(f"Warning: could not parse article — {e}")
    return articles


def summarize_with_claude(topic: str, articles: list[dict]) -> str:
    """Ask Claude to generate a digest summary for a set of articles."""
    if not ANTHROPIC_API_KEY:
        return "⚠️ ANTHROPIC_API_KEY not set — summaries unavailable."

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"""
Article {i}: {a['title']}
Authors: {', '.join(a['authors'])}
Journal: {a['journal']} ({a['pub_date']})
Abstract: {a['abstract'][:800]}
---"""

    prompt = f"""You are a scientific digest assistant. Summarize these new PubMed publications on the topic "{topic}".

For each article, write 2-3 sentences explaining:
- What the study did
- The key finding
- Why it matters

Keep language accessible but scientifically accurate. Be concise.

{articles_text}

Return a numbered list, one entry per article."""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"]


def generate_html(digest_data: dict) -> str:
    """Generate the full HTML dashboard page."""
    date_str = digest_data["date"]
    topics_html = ""

    for entry in digest_data["topics"]:
        topic = entry["topic"]
        articles = entry["articles"]
        summary = entry["summary"]
        count = len(articles)

        if count == 0:
            articles_html = "<p class='no-results'>No new articles found today.</p>"
            summary_html = ""
        else:
            articles_html = ""
            for a in articles:
                authors_str = ", ".join(a["authors"])
                articles_html += f"""
                <div class="article-card">
                    <a class="article-title" href="{a['url']}" target="_blank">{a['title']}</a>
                    <div class="article-meta">{authors_str} &mdash; <em>{a['journal']}</em> {a['pub_date']}</div>
                </div>"""
            summary_html = f"""
            <div class="summary-box">
                <h3>🤖 AI Summary</h3>
                <div class="summary-text">{summary.replace(chr(10), '<br>')}</div>
            </div>"""

        topics_html += f"""
        <section class="topic-section">
            <div class="topic-header">
                <h2>{topic}</h2>
                <span class="badge">{count} new article{'s' if count != 1 else ''}</span>
            </div>
            {summary_html}
            <div class="articles-list">{articles_html}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PubMed Daily Digest — {date_str}</title>
<style>
  :root {{
    --bg: #f8f9fc;
    --card: #ffffff;
    --primary: #2563eb;
    --primary-light: #eff6ff;
    --text: #1e293b;
    --muted: #64748b;
    --border: #e2e8f0;
    --badge-bg: #dbeafe;
    --badge-text: #1d4ed8;
    --summary-bg: #f0fdf4;
    --summary-border: #86efac;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  header {{ background: var(--primary); color: white; padding: 2rem; text-align: center; }}
  header h1 {{ font-size: 1.8rem; font-weight: 700; }}
  header p {{ opacity: 0.85; margin-top: 0.3rem; }}
  main {{ max-width: 860px; margin: 2rem auto; padding: 0 1rem; }}
  .topic-section {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }}
  .topic-header {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }}
  .topic-header h2 {{ font-size: 1.2rem; color: var(--primary); }}
  .badge {{ background: var(--badge-bg); color: var(--badge-text); font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 999px; white-space: nowrap; }}
  .summary-box {{ background: var(--summary-bg); border-left: 4px solid var(--summary-border); border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.2rem; }}
  .summary-box h3 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #16a34a; margin-bottom: 0.5rem; }}
  .summary-text {{ font-size: 0.92rem; color: var(--text); }}
  .article-card {{ border-top: 1px solid var(--border); padding: 0.9rem 0; }}
  .article-card:first-child {{ border-top: none; }}
  .article-title {{ font-weight: 600; color: var(--primary); text-decoration: none; font-size: 0.95rem; }}
  .article-title:hover {{ text-decoration: underline; }}
  .article-meta {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.2rem; }}
  .no-results {{ color: var(--muted); font-style: italic; font-size: 0.9rem; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 2rem; }}
</style>
</head>
<body>
<header>
  <h1>📄 PubMed Daily Digest</h1>
  <p>{date_str} &mdash; Generated automatically via GitHub Actions + Claude AI</p>
</header>
<main>
{topics_html}
</main>
<footer>Powered by NCBI PubMed E-utilities &amp; Anthropic Claude API</footer>
</body>
</html>"""


def run():
    today = datetime.date.today().strftime("%Y-%m-%d")
    digest_data = {"date": today, "topics": []}

    for topic in TOPICS:
        print(f"🔍 Fetching: {topic}")
        pmids = search_pubmed(topic, DAYS_BACK, MAX_RESULTS_PER_TOPIC)
        articles = fetch_article_details(pmids)
        print(f"   Found {len(articles)} articles")

        summary = ""
        if articles:
            print(f"   Summarizing with Claude...")
            summary = summarize_with_claude(topic, articles)

        digest_data["topics"].append({
            "topic": topic,
            "articles": articles,
            "summary": summary,
        })

    # Save JSON (for history/debugging)
    os.makedirs("docs/data", exist_ok=True)
    with open(f"docs/data/{today}.json", "w") as f:
        json.dump(digest_data, f, indent=2)

    # Save HTML dashboard
    html = generate_html(digest_data)
    with open("docs/index.html", "w") as f:
        f.write(html)

    print(f"✅ Digest generated for {today}")


if __name__ == "__main__":
    run()
