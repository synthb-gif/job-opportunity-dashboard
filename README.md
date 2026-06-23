# AI Opportunity Verification & Matching Dashboard

A Streamlit web app that helps job seekers discover **safe, verified employment opportunities**. Powered by Google Gemini for AI-assisted matching, quality assessment, and scam detection — with rule-based fallbacks when no API key is provided.

## Features

- **Curated profile inputs** — autocomplete from 50 vetted skills + 30 career interests (no free-text noise).
- **Work preference** — "All", Remote, Hybrid, or On-site. "All" disables filtering.
- **Three ways to add opportunities**:
  - Browse 27 pre-loaded sample roles (Kenya + remote/global).
  - Paste a job description — auto-extracts Title / Employer / Location, falls back to a form for missing fields.
  - Manually fill in a structured form.
- **Trusted Job Sources** (collapsible) — curated local + international job boards as clickable links. *No scraping.*
- **AI scoring pipeline** — Match (0–100), QA (0–100), Trust (0–100), Risk (Low/Medium/High).
- **Final score** = `0.4 × Match + 0.4 × QA + 0.2 × Trust`. High-risk postings are forced to 0 and hidden by default.
- **Progress indicator** during AI scoring, plus pool counter showing opportunities ready to match.
- **Analytics tab** — totals, averages, top sources, common risk indicators.

## Project structure

```
streamlit-opportunity-app/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── data/
    └── sample_opportunities.csv
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env and add your Gemini key
export GEMINI_API_KEY=your_key_here
streamlit run app.py
```

Get a free Gemini key at https://aistudio.google.com/app/apikey.

> The app works without a key (rule-based mode) but AI scoring is disabled.

## Deploy to Streamlit Community Cloud

1. Push this folder to a public GitHub repo.
2. Go to https://share.streamlit.io and create a new app pointing to `app.py`.
3. Under **Settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   ```
4. Deploy.

## Scoring formula

| Component | Weight | What it measures |
|-----------|--------|------------------|
| Match     | 40%    | Skills + interests alignment |
| QA        | 40%    | Completeness of the posting |
| Trust     | 20%    | Reputation of the source board |
| Risk      | gate   | If High → Final = 0 |

## Notes

- Skills list is **fixed at 50 entries** and interests at **30** — custom entries are not allowed by design.
- The app does **not** scrape external job boards; trusted boards are surfaced as outbound links.
- Sample data is in `data/sample_opportunities.csv` — edit freely.
