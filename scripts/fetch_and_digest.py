#!/usr/bin/env python3
"""
PubMed Daily Digest Generator
Fetches new PubMed articles, classifies study types, and generates structured
clinical summaries via Claude API. Outputs a color-coded HTML dashboard.
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
    '((adherence OR persistence OR switch OR discontinue) AND (GLP-1 OR "GLP-1 RA"))',
]

MAX_RESULTS_PER_TOPIC = 20
DAYS_BACK = 3
# ─────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")


def build_date_filter(days_back):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days_back)
    return f"{start.strftime('%Y/%m/%d')}:{today.strftime('%Y/%m/%d')}[dp]"


def search_pubmed(topic, days_back, max_results):
    date_filter = build_date_filter(days_back)
    query = f"({topic}) AND {date_filter}"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json", "sort": "date"}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_article_details(pmids):
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
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
                "pmid": pmid, "title": title, "abstract": abstract, "authors": authors,
                "journal": journal, "pub_date": f"{month} {year}".strip(),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception as e:
            print(f"Warning: could not parse article — {e}")
    return articles


def summarize_with_claude(topic, articles):
    if not ANTHROPIC_API_KEY:
        return [{"study_type": "Unknown", "study_type_category": "original", "sample_size": "N/A",
                 "population": "N/A", "medications": "N/A", "country_dataset": "N/A",
                 "key_findings": "API key not set."} for _ in articles]

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\nARTICLE_{i}:\nTitle: {a['title']}\nJournal: {a['journal']} ({a['pub_date']})\nAbstract: {a['abstract'][:600]}\n---"

    prompt = f"""You are a clinical research summarizer. Analyze each PubMed article below on "{topic}".

For EACH article, extract the following and return as a JSON array.
Return ONLY a valid JSON array, no markdown, no backticks, no explanation.

Fields:
- "study_type": Specific design (e.g. "RCT", "Meta-analysis", "Systematic review", "Cohort study", "Narrative review", "Secondary analysis of RCT", "Real-world study", "Cross-sectional study")
- "study_type_category": MUST be exactly "review" (for any review/meta-analysis/systematic review) OR "original" (for RCTs, cohorts, real-world, secondary analyses)
- "sample_size": e.g. "n=101", "23 RCTs", "Not reported"
- "population": Disease + key patient characteristics (e.g. "Adults with T2DM and CKD")
- "medications": Specific drugs and comparators (e.g. "Liraglutide vs placebo")
- "country_dataset": Country/region or dataset name (e.g. "Taiwan", "Not reported")
- "key_findings": 2-3 most important results as one concise paragraph

{articles_text}

Return a JSON array with exactly {len(articles)} objects in the same order as the articles."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    raw = result["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def generate_html(digest_data):
    date_str = digest_data["date"]
    topics_html = ""

    for entry in digest_data["topics"]:
        topic = entry["topic"]
        articles = entry["articles"]
        summaries = entry.get("summaries", [])
        count = len(articles)

        if count == 0:
            articles_html = "<p class='no-results'>No new articles found in the last 3 days.</p>"
            review_count = original_count = 0
        else:
            articles_html = ""
            review_count = sum(1 for s in summaries if s.get("study_type_category") == "review")
            original_count = count - review_count

            for i, a in enumerate(articles):
                s = summaries[i] if i < len(summaries) else {}
                category = s.get("study_type_category", "original")
                study_type = s.get("study_type", "Unknown")
                sample_size = s.get("sample_size", "Not reported")
                population = s.get("population", "Not reported")
                medications = s.get("medications", "Not reported")
                country = s.get("country_dataset", "Not reported")
                findings = s.get("key_findings", "Not available.")

                if category == "review":
                    border_color, bg_color, badge_class = "#f59e0b", "#fffdf0", "badge-review"
                else:
                    border_color, bg_color, badge_class = "#3b82f6", "#f0f6ff", "badge-original"

                authors_str = ", ".join(a["authors"])
                articles_html += f"""
                <div class="article-card" style="border-left:4px solid {border_color};background:{bg_color};">
                  <div class="article-header">
                    <span class="study-badge {badge_class}">{study_type}</span>
                    <span class="sample-size">👥 {sample_size}</span>
                  </div>
                  <a class="article-title" href="{a['url']}" target="_blank">{a['title']}</a>
                  <div class="article-meta">{authors_str} &mdash; <em>{a['journal']}</em> {a['pub_date']}</div>
                  <div class="article-details">
                    <div class="detail-row"><span class="detail-label">🏥 Population</span><span class="detail-value">{population}</span></div>
                    <div class="detail-row"><span class="detail-label">💊 Medications</span><span class="detail-value">{medications}</span></div>
                    <div class="detail-row"><span class="detail-label">🌍 Country / Dataset</span><span class="detail-value">{country}</span></div>
                    <div class="detail-row findings-row"><span class="detail-label">🔬 Key Findings</span><span class="detail-value findings-text">{findings}</span></div>
                  </div>
                </div>"""

        topics_html += f"""
        <section class="topic-section">
          <div class="topic-header">
            <h2>{topic}</h2>
            <div class="topic-badges">
              <span class="badge">{count} articles</span>
              <span class="badge badge-original-sm">🔵 {original_count} original</span>
              <span class="badge badge-review-sm">🟡 {review_count} reviews / meta-analyses</span>
            </div>
          </div>
          <div class="articles-list">{articles_html}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PubMed Digest — {date_str}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b;line-height:1.6}}
  header{{background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:2rem;text-align:center}}
  header h1{{font-size:1.8rem;font-weight:700}}
  header p{{opacity:.85;margin-top:.3rem;font-size:.9rem}}
  .legend{{display:flex;gap:1.5rem;justify-content:center;margin-top:1rem;font-size:.8rem;flex-wrap:wrap}}
  .legend-item{{display:flex;align-items:center;gap:.4rem}}
  .legend-dot{{width:12px;height:12px;border-radius:50%;display:inline-block}}
  main{{max-width:920px;margin:2rem auto;padding:0 1rem}}
  .topic-section{{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
  .topic-header{{display:flex;align-items:center;flex-wrap:wrap;gap:.8rem;margin-bottom:1.2rem;padding-bottom:1rem;border-bottom:2px solid #e2e8f0}}
  .topic-header h2{{font-size:1rem;color:#1e40af;flex:1;word-break:break-word}}
  .topic-badges{{display:flex;gap:.5rem;flex-wrap:wrap}}
  .badge{{background:#dbeafe;color:#1d4ed8;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:999px}}
  .badge-original-sm{{background:#eff6ff;color:#1d4ed8;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:999px}}
  .badge-review-sm{{background:#fffbeb;color:#92400e;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:999px}}
  .article-card{{border-radius:10px;padding:1.1rem 1.2rem;margin-bottom:1rem;border:1px solid #e2e8f0}}
  .article-header{{display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;flex-wrap:wrap}}
  .study-badge{{font-size:.7rem;font-weight:700;padding:.2rem .7rem;border-radius:999px;text-transform:uppercase;letter-spacing:.03em}}
  .badge-review{{background:#fef3c7;color:#92400e;border:1px solid #f59e0b}}
  .badge-original{{background:#dbeafe;color:#1e40af;border:1px solid #3b82f6}}
  .sample-size{{font-size:.78rem;color:#64748b;font-weight:500}}
  .article-title{{font-weight:700;color:#1e40af;text-decoration:none;font-size:.97rem;display:block;margin-bottom:.3rem;line-height:1.4}}
  .article-title:hover{{text-decoration:underline}}
  .article-meta{{font-size:.78rem;color:#64748b;margin-bottom:.8rem}}
  .article-details{{display:flex;flex-direction:column;gap:.45rem}}
  .detail-row{{display:flex;gap:.6rem;font-size:.84rem}}
  .detail-label{{font-weight:600;color:#64748b;min-width:150px;flex-shrink:0}}
  .detail-value{{color:#1e293b}}
  .findings-row{{margin-top:.4rem;padding-top:.5rem;border-top:1px dashed #e2e8f0}}
  .findings-text{{font-style:italic;color:#334155}}
  .no-results{{color:#64748b;font-style:italic;font-size:.9rem}}
  footer{{text-align:center;color:#64748b;font-size:.8rem;padding:2rem}}
  @media(max-width:600px){{.detail-label{{min-width:110px}}.detail-row{{flex-direction:column;gap:.1rem}}}}
</style>
</head>
<body>
<header>
  <h1>📄 PubMed Digest</h1>
  <p>{date_str} &mdash; Last 3 days &mdash; Auto-generated via GitHub Actions + Claude AI</p>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div>Original Study (RCT, Cohort, Real-world…)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>Review / Meta-analysis / Systematic Review</div>
  </div>
</header>
<main>{topics_html}</main>
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
        summaries = []
        if articles:
            print("   Summarizing with Claude...")
            summaries = summarize_with_claude(topic, articles)
        digest_data["topics"].append({"topic": topic, "articles": articles, "summaries": summaries})

    os.makedirs("docs/data", exist_ok=True)
    with open(f"docs/data/{today}.json", "w") as f:
        json.dump(digest_data, f, indent=2)

    html = generate_html(digest_data)
    with open("docs/index.html", "w") as f:
        f.write(html)

    print(f"✅ Digest generated for {today}")


if __name__ == "__main__":
    run()
