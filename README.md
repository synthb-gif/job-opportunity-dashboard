# AI Opportunity Verification & Matching Dashboard

A Streamlit app that helps job seekers discover **safe, verified** employment opportunities using Google Gemini for AI matching, quality assurance, and scam detection.

## Features
- Job-seeker profile builder
- CSV upload or paste-a-posting input
- AI Match Score, QA Score, Trust Score, Risk Level, Final Score
- Color-coded result cards (✅ ⚠️ 🚫)
- Analytics dashboard (sources, risk indicators, approval rate)

## Quick start (local)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here   # Windows: set GEMINI_API_KEY=...
streamlit run app.py
```

Get a free Gemini API key at https://aistudio.google.com/app/apikey

If the key is missing the app still runs using **rule-based analysis only** and shows a clear warning.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. Go to https://share.streamlit.io → "New app" → pick your repo and `app.py`.
3. Under **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   ```
4. Deploy.

## Testing
Use `sample_opportunities.csv` (5 example postings — includes legitimate roles and intentional scam patterns to demonstrate detection).

## Scoring
`Final Score = 0.4 * Match + 0.4 * QA + 0.2 * Trust`
If risk is **High**, final score is forced to 0 and the card is hidden by default.

## CSV format
Columns: `Job Title, Employer, Location, Description, Requirements, Application Link, Source, Deadline`
