"""
AI Opportunity Verification and Matching Dashboard
Streamlit app powered by Google Gemini for safe, verified job discovery.
"""
import os
import re
import json
import io
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

# ---------- Gemini setup ----------
GEMINI_AVAILABLE = True
try:
    import google.generativeai as genai
except Exception:
    GEMINI_AVAILABLE = False

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            key = ""
    return key

def get_gemini_model():
    if not GEMINI_AVAILABLE:
        return None
    key = get_api_key()
    if not key:
        return None
    try:
        genai.configure(api_key=key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        return None

# ---------- Trusted source registry ----------
TRUSTED_SOURCES = {
    "fuzu.com": 100,
    "reliefweb.int": 100,
    "unjobnet.org": 100,
    "unv.org": 100,
    "idealist.org": 90,
    "climatebase.org": 90,
    "remoteok.com": 90,
    "weworkremotely.com": 90,
    "brightermonday.co.ke": 75,
    "myjobmag.co.ke": 75,
}

FREE_EMAIL_PROVIDERS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]

# ---------- Helpers ----------
def get_trust_score(source: str, link: str = "") -> int:
    candidates = []
    if source:
        candidates.append(source.lower())
    if link:
        try:
            host = urlparse(link).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            candidates.append(host)
        except Exception:
            pass
    for c in candidates:
        for domain, score in TRUSTED_SOURCES.items():
            if domain in c:
                return score
    return 50

def safe_json_from_text(text: str):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            cleaned = m.group(0).replace("\n", " ")
            return json.loads(cleaned)
        except Exception:
            return None

# ---------- Rule-based QA ----------
def rule_based_qa(opp: dict):
    strengths, weaknesses = [], []
    score = 0
    employer = (opp.get("Employer") or "").strip()
    desc = (opp.get("Description") or "").strip()
    reqs = (opp.get("Requirements") or "").strip()
    link = (opp.get("Application Link") or "").strip()
    deadline = (opp.get("Deadline") or "").strip()
    text_all = f"{desc} {reqs}".lower()

    if employer and len(employer) > 2:
        strengths.append("Employer clearly identified"); score += 17
    else:
        weaknesses.append("Employer is missing or unclear")

    if len(desc.split()) >= 20:
        strengths.append("Responsibilities described"); score += 17
    else:
        weaknesses.append("Responsibilities not well described")

    if reqs and len(reqs.split()) >= 5:
        strengths.append("Requirements listed"); score += 17
    else:
        weaknesses.append("Requirements are missing or sparse")

    if link or "apply" in text_all or "email" in text_all:
        strengths.append("Application method explained"); score += 17
    else:
        weaknesses.append("No clear application method")

    if re.search(r"(salary|ksh|usd|\$|compensation|stipend|pay)", text_all):
        strengths.append("Salary/compensation mentioned"); score += 16
    else:
        weaknesses.append("No salary or compensation information")

    if deadline:
        strengths.append("Deadline specified"); score += 16
    else:
        weaknesses.append("No application deadline specified")

    return min(score, 100), strengths, weaknesses

# ---------- Rule-based scam detection ----------
def rule_based_scam(opp: dict):
    flags = []
    desc = (opp.get("Description") or "")
    reqs = (opp.get("Requirements") or "")
    employer = (opp.get("Employer") or "").strip()
    link = (opp.get("Application Link") or "")
    text = f"{desc} {reqs} {link}".lower()

    if re.search(r"(pay\s+(a\s+)?fee|registration fee|application fee|send\s+\$?\d+|processing fee)", text):
        flags.append("Requests payment or application fees")

    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    for e in emails:
        domain = e.split("@")[-1].lower()
        if domain in FREE_EMAIL_PROVIDERS:
            flags.append(f"Uses free email provider ({domain})")
            break

    if not employer:
        flags.append("Missing employer name")

    if re.search(r"(\$\s?[5-9]\d{3,}|\$\s?\d{5,})\s*(per\s+week|/week|weekly|per\s+day|/day)", text):
        flags.append("Unrealistic salary promise")
    if re.search(r"earn\s+\$?\d{3,}\s+(daily|per day|a day)", text):
        flags.append("Unrealistic daily earnings claim")

    if len(desc.split()) < 30:
        flags.append("Vague job description (under 30 words)")

    if re.search(r"\b(u|ur|plz|pls|kindly do the needful)\b", text):
        flags.append("Poor grammar suggesting fraud")

    if not re.search(r"https?://", link) and "website" not in text and "company" not in text:
        flags.append("No company website mentioned")

    if len(flags) >= 3:
        risk = "High"
    elif len(flags) >= 1:
        risk = "Medium"
    else:
        risk = "Low"
    return risk, flags

# ---------- Gemini-enhanced analyses ----------
def gemini_match(profile: dict, opp: dict, model):
    if model is None:
        return _fallback_match(profile, opp)
    prompt = f"""You evaluate job fit. Return ONLY JSON.
Profile: {json.dumps(profile)}
Opportunity: {json.dumps({k: opp.get(k, '') for k in ['Job Title','Employer','Location','Description','Requirements']})}
Return JSON: {{"match_score": <0-100 int>, "reasoning": ["bullet1","bullet2","bullet3"], "summary": "2-3 sentence plain-language summary"}}
Evaluate skill alignment, experience alignment, location fit, career interest alignment."""
    try:
        resp = model.generate_content(prompt)
        data = safe_json_from_text(resp.text)
        if data and "match_score" in data:
            return int(data.get("match_score", 0)), data.get("reasoning", []), data.get("summary", "")
    except Exception as e:
        st.session_state.setdefault("_gemini_errors", []).append(str(e))
    return _fallback_match(profile, opp)

def _fallback_match(profile, opp):
    skills = [s.lower() for s in profile.get("skills", [])]
    interests = [s.lower() for s in profile.get("interests", [])]
    text = f"{opp.get('Job Title','')} {opp.get('Description','')} {opp.get('Requirements','')}".lower()
    skill_hits = sum(1 for s in skills if s and s in text)
    interest_hits = sum(1 for s in interests if s and s in text)
    score = min(100, (skill_hits * 12) + (interest_hits * 15) + 30)
    reasoning = [
        f"Matched {skill_hits} of your skills in the description",
        f"Matched {interest_hits} of your career interests",
        f"Location preference: {profile.get('work_pref','')}",
    ]
    return score, reasoning, f"{opp.get('Job Title','This role')} at {opp.get('Employer','the employer')} appears partially aligned with your profile."

def gemini_qa_enhance(opp, base_score, strengths, weaknesses, model):
    if model is None:
        return base_score, strengths, weaknesses
    prompt = f"""Assess job posting quality. Return ONLY JSON.
Posting: {json.dumps({k: opp.get(k,'') for k in ['Job Title','Employer','Location','Description','Requirements','Application Link','Deadline']})}
Rule-based score: {base_score}. Strengths: {strengths}. Weaknesses: {weaknesses}.
Return JSON: {{"qa_score": <0-100>, "strengths": [..], "weaknesses": [..]}}"""
    try:
        resp = model.generate_content(prompt)
        data = safe_json_from_text(resp.text)
        if data and "qa_score" in data:
            return int(data["qa_score"]), data.get("strengths", strengths), data.get("weaknesses", weaknesses)
    except Exception:
        pass
    return base_score, strengths, weaknesses

def gemini_scam_enhance(opp, base_risk, base_flags, model):
    if model is None:
        return base_risk, base_flags
    prompt = f"""Assess job scam risk. Return ONLY JSON.
Posting: {json.dumps({k: opp.get(k,'') for k in ['Job Title','Employer','Description','Requirements','Application Link']})}
Rule-based risk: {base_risk}. Flags: {base_flags}.
Return JSON: {{"risk_level": "Low|Medium|High", "explanations": [..]}}"""
    try:
        resp = model.generate_content(prompt)
        data = safe_json_from_text(resp.text)
        if data and "risk_level" in data:
            risk = data["risk_level"]
            if risk not in ("Low", "Medium", "High"):
                risk = base_risk
            return risk, data.get("explanations", base_flags)
    except Exception:
        pass
    return base_risk, base_flags

# ---------- Analysis pipeline ----------
def analyze_opportunity(opp, profile, model):
    qa_score, strengths, weaknesses = rule_based_qa(opp)
    qa_score, strengths, weaknesses = gemini_qa_enhance(opp, qa_score, strengths, weaknesses, model)
    risk, flags = rule_based_scam(opp)
    risk, flags = gemini_scam_enhance(opp, risk, flags, model)
    match_score, reasoning, summary = gemini_match(profile, opp, model)
    trust = get_trust_score(opp.get("Source", ""), opp.get("Application Link", ""))
    final = round(0.4 * match_score + 0.4 * qa_score + 0.2 * trust, 1)
    if risk == "High":
        final = 0
    return {
        "opp": opp,
        "match_score": match_score,
        "qa_score": qa_score,
        "trust_score": trust,
        "risk": risk,
        "final_score": final,
        "reasoning": reasoning,
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "flags": flags,
    }

# ---------- Parsing manual paste ----------
def parse_pasted_text(text):
    def grab(label):
        m = re.search(rf"{label}\s*[:\-]\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
    return {
        "Job Title": grab("Job Title") or grab("Title") or "Untitled Opportunity",
        "Employer": grab("Employer") or grab("Company") or "",
        "Location": grab("Location") or "",
        "Description": grab("Description") or text,
        "Requirements": grab("Requirements") or "",
        "Application Link": grab("Application Link") or grab("Link") or grab("Apply") or "",
        "Source": grab("Source") or "",
        "Deadline": grab("Deadline") or "",
    }

# ---------- UI ----------
st.set_page_config(page_title="AI Opportunity Verification Dashboard", page_icon="✅", layout="wide")

if "profile" not in st.session_state:
    st.session_state.profile = None
if "results" not in st.session_state:
    st.session_state.results = []
if "show_high_risk" not in st.session_state:
    st.session_state.show_high_risk = False

st.title("✅ AI Opportunity Verification & Matching Dashboard")
st.caption("Discover safe, verified employment opportunities — powered by Google Gemini.")

# API key warning
if not get_api_key():
    st.warning(
        "⚠️ **GEMINI_API_KEY not set.** The app will run with rule-based analysis only. "
        "To enable AI scoring, get a free key at https://aistudio.google.com/app/apikey and set "
        "`GEMINI_API_KEY` as an environment variable or in `.streamlit/secrets.toml`."
    )

tab1, tab2 = st.tabs(["🔍 Find Opportunities", "📊 Analytics"])

with tab1:
    st.header("Step 1 — Your Profile")
    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name")
            location = st.text_input("Location")
            education = st.selectbox("Highest Education Level",
                ["High School", "Diploma", "Bachelor's", "Master's", "PhD"])
            years = st.number_input("Years of Experience", 0, 50, 1)
        with c2:
            default_skills = ["Excel", "Google Sheets", "Data Collection", "KoboToolbox", "Reporting"]
            skills = st.multiselect("Skills", default_skills, default=default_skills)
            extra_skills = st.text_input("Add custom skills (comma-separated)")
            default_interests = ["Research Assistant", "Data Analyst", "M&E Assistant"]
            interests = st.multiselect("Career Interests", default_interests, default=default_interests)
            extra_interests = st.text_input("Add custom interests (comma-separated)")
            work_pref = st.radio("Work Preference", ["Remote", "Hybrid", "On-site"], horizontal=True)
        accessibility = st.text_area("Accessibility Requirements (optional)")
        submitted = st.form_submit_button("Find Opportunities", type="primary")
    if submitted:
        if extra_skills:
            skills += [s.strip() for s in extra_skills.split(",") if s.strip()]
        if extra_interests:
            interests += [s.strip() for s in extra_interests.split(",") if s.strip()]
        st.session_state.profile = {
            "name": name, "location": location, "education": education,
            "years": years, "skills": skills, "interests": interests,
            "work_pref": work_pref, "accessibility": accessibility,
        }
        st.success(f"Profile saved for {name or 'you'}. Now add opportunities below.")

    if st.session_state.profile:
        st.header("Step 2 — Add Opportunities")
        method = st.radio("Input method", ["Upload CSV", "Paste job description"], horizontal=True)
        opps = []
        if method == "Upload CSV":
            up = st.file_uploader("CSV with: Job Title, Employer, Location, Description, Requirements, Application Link, Source, Deadline", type=["csv"])
            if up:
                try:
                    df = pd.read_csv(up).fillna("")
                    opps = df.to_dict(orient="records")
                except Exception as e:
                    st.error(f"Could not read CSV: {e}")
        else:
            pasted = st.text_area("Paste a job description", height=200)
            if pasted.strip():
                opps = [parse_pasted_text(pasted)]

        if opps:
            st.info(f"**{len(opps)} Opportunities Found**")
            if st.button("🤖 Analyze with AI", type="primary"):
                model = get_gemini_model()
                results = []
                prog = st.progress(0)
                for i, opp in enumerate(opps):
                    results.append(analyze_opportunity(opp, st.session_state.profile, model))
                    prog.progress((i + 1) / len(opps))
                st.session_state.results = sorted(results, key=lambda r: r["final_score"], reverse=True)
                st.success("Analysis complete!")

    # Results
    if st.session_state.results:
        st.header("Step 3 — Ranked Opportunities")
        st.checkbox("Show high-risk opportunities", key="show_high_risk")
        for r in st.session_state.results:
            if r["risk"] == "High" and not st.session_state.show_high_risk:
                st.error(f"🚫 Hidden high-risk posting: **{r['opp'].get('Job Title','Untitled')}** — enable the checkbox above to view.")
                continue
            color = "#16a34a" if r["risk"] == "Low" else ("#ca8a04" if r["risk"] == "Medium" else "#dc2626")
            icon = "✅" if r["risk"] == "Low" else ("⚠️" if r["risk"] == "Medium" else "🚫")
            with st.container(border=True):
                st.markdown(
                    f"<div style='border-left:6px solid {color}; padding-left:12px'>"
                    f"<h3 style='margin:0'>{icon} {r['opp'].get('Job Title','Untitled')}</h3>"
                    f"<p style='margin:2px 0;color:#555'>{r['opp'].get('Employer','')} · {r['opp'].get('Location','')}</p>"
                    f"</div>", unsafe_allow_html=True)
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Match", f"{r['match_score']}")
                c2.metric("QA", f"{r['qa_score']}")
                c3.metric("Trust", f"{r['trust_score']}")
                c4.metric("Risk", r["risk"])
                c5.metric("Final", f"{r['final_score']}")
                st.write(r["summary"])
                with st.expander("Why this match?"):
                    for b in r["reasoning"]:
                        st.write(f"• {b}")
                with st.expander("Quality strengths & weaknesses"):
                    st.write("**Strengths**")
                    for s in r["strengths"]: st.write(f"✅ {s}")
                    st.write("**Weaknesses**")
                    for w in r["weaknesses"]: st.write(f"⚠️ {w}")
                if r["flags"]:
                    with st.expander(f"Risk indicators ({len(r['flags'])})"):
                        for f in r["flags"]: st.write(f"🚩 {f}")
                link = r["opp"].get("Application Link", "")
                if link:
                    st.link_button("Apply →", link)

with tab2:
    st.header("📊 Analytics")
    results = st.session_state.results
    if not results:
        st.info("Run an analysis on the first tab to see analytics.")
    else:
        approved = [r for r in results if r["risk"] != "High" and r["final_score"] >= 60]
        rejected = [r for r in results if r not in approved]
        high_risk = [r for r in results if r["risk"] == "High"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Reviewed", len(results))
        c2.metric("Avg QA Score", round(sum(r["qa_score"] for r in results) / len(results), 1))
        c3.metric("Avg Match Score", round(sum(r["match_score"] for r in results) / len(results), 1))
        c4, c5 = st.columns(2)
        c4.metric("Approved vs Rejected", f"{len(approved)} / {len(rejected)}")
        c5.metric("High Risk Detected", len(high_risk))

        st.subheader("Top Opportunity Sources")
        srcs = {}
        for r in results:
            s = r["opp"].get("Source") or "Unknown"
            srcs[s] = srcs.get(s, 0) + 1
        st.bar_chart(pd.DataFrame({"count": srcs}))

        st.subheader("Common Risk Indicators")
        flag_counts = {}
        for r in results:
            for f in r["flags"]:
                flag_counts[f] = flag_counts.get(f, 0) + 1
        if flag_counts:
            st.bar_chart(pd.DataFrame({"count": flag_counts}))
        else:
            st.write("No risk indicators detected. 🎉")
