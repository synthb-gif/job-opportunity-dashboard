"""
AI Opportunity Verification and Matching Dashboard
Streamlit app powered by Google Gemini for safe, verified job discovery.
"""
import os
import re
import json
from datetime import date
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


# ---------- Controlled vocabularies ----------
SKILLS_OPTIONS = [
    "Microsoft Excel", "Google Sheets", "Google Workspace", "Data Collection",
    "KoboToolbox", "Data Analysis", "Data Visualization", "Statistical Analysis",
    "SPSS", "R Programming", "Python", "SQL", "Tableau", "Power BI",
    "Research Methods", "Report Writing", "Proposal Writing", "Grant Writing",
    "Monitoring & Evaluation (M&E)", "Project Management", "Budget Management",
    "Financial Analysis", "Accounting", "Bookkeeping", "QuickBooks",
    "Human Resources", "Recruitment", "Training & Facilitation",
    "Community Engagement", "Stakeholder Management", "Communications",
    "Social Media Management", "Content Creation", "Graphic Design", "Canva",
    "Adobe Creative Suite", "Web Development", "HTML/CSS", "JavaScript",
    "UI/UX Design", "Figma", "Digital Marketing", "SEO", "Email Marketing",
    "CRM Management", "Salesforce", "Customer Service",
    "Supply Chain Management", "Logistics Coordination", "GIS & Mapping",
]

INTERESTS_OPTIONS = [
    "Research Assistant", "Data Analyst", "Monitoring & Evaluation Officer",
    "Project Manager", "Program Coordinator", "Finance Officer", "Accountant",
    "Human Resources Officer", "Communications Officer", "Social Media Manager",
    "Content Creator", "Graphic Designer", "Web Developer", "UI/UX Designer",
    "Digital Marketing Specialist", "Customer Success Manager",
    "Sales Representative", "Business Development Officer", "Grant Writer",
    "Proposal Writer", "Consultant", "Field Officer", "Community Liaison Officer",
    "Logistics Coordinator", "Supply Chain Manager", "GIS Specialist",
    "Policy Analyst", "Advocacy Officer", "Training Coordinator",
    "Administrative Assistant",
]

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
    "workingnomads.com": 85,
    "flexjobs.com": 85,
    "brightermonday.co.ke": 75,
    "myjobmag.co.ke": 75,
    "careerjet.co.ke": 70,
}

LOCAL_JOB_BOARDS = [
    ("MyJobMag Kenya", "https://www.myjobmag.co.ke/search/jobs?"),
    ("Fuzu", "https://www.fuzu.com/job"),
    ("CampusBiz", "https://campusbiz.co.ke/careers/jobs-in-kenya/"),
    ("Elevolt", "https://jobs.elevolt.co.ke/jobs"),
    ("ReliefWeb", "https://reliefweb.int/jobs"),
    ("UN JobNet", "https://www.unjobnet.org/jobs"),
    ("Idealist", "https://www.idealist.org/en/jobs"),
    ("OpenedCareer", "https://openedcareer.com/category/jobs/"),
    ("BrighterMonday", "https://www.brightermonday.co.ke/jobs"),
    ("Opportunity Desk", "https://opportunitydesk.org/category/jobs-and-internships/"),
    ("GAA Kenya", "https://gaa.go.ke/job-adverts"),
]

REMOTE_JOB_BOARDS = [
    ("Remote Rocketship", "https://www.remoterocketship.com/"),
    ("Acquia", "https://www.acquia.com/careers/open-positions"),
    ("90 Seconds", "https://90seconds.com/about/careers/positions/"),
    ("Wellfound", "https://wellfound.com/company"),
    ("37signals", "https://37signals.com/jobs"),
    ("Fueled", "https://fueled.com/careers/"),
    ("Adzuna", "https://www.adzuna.co.uk/jobs/careers"),
    ("Actabl", "https://recruiting.paylocity.com/recruiting/jobs/All/df0b4c2b-4424-4d43-97ac-9cf7f31153d5/Actabl"),
    ("Alight", "https://careers.alight.com/us/en"),
    ("Andela", "https://jobs.ashbyhq.com/andela"),
    ("Appcues", "https://www.appcues.com/careers"),
    ("Applaudo", "https://applaudo.com/en/careers/"),
    ("AppliedAI", "https://app.whitecarrot.io/careers/appliedai"),
    ("Appwrite", "https://www.appwrite.careers/"),
    ("Argyle", "https://ats.rippling.com/argyle/jobs"),
    ("Articulate", "https://www.articulate.com/about/careers/"),
    ("Asana", "https://asana.com/jobs/all"),
    ("Confluent", "https://careers.confluent.io/jobs"),
]

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
            return json.loads(m.group(0).replace("\n", " "))
        except Exception:
            return None


# ---------- Rule-based QA ----------
def rule_based_qa(opp: dict):
    strengths, weaknesses, score = [], [], 0
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


def rule_based_scam(opp: dict):
    flags = []
    desc = opp.get("Description") or ""
    reqs = opp.get("Requirements") or ""
    employer = (opp.get("Employer") or "").strip()
    link = opp.get("Application Link") or ""
    text = f"{desc} {reqs} {link}".lower()

    if re.search(r"(pay\s+(a\s+)?fee|registration fee|application fee|send\s+\$?\d+|processing fee)", text):
        flags.append("Requests payment or application fees")
    for e in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        if e.split("@")[-1].lower() in FREE_EMAIL_PROVIDERS:
            flags.append(f"Uses free email provider ({e.split('@')[-1].lower()})")
            break
    if not employer:
        flags.append("Missing employer name")
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
def gemini_match(profile, opp, model):
    if model is None:
        return _fallback_match(profile, opp)
    prompt = f"""You evaluate job fit. Return ONLY JSON.
Profile: {json.dumps(profile)}
Opportunity: {json.dumps({k: opp.get(k, '') for k in ['Job Title','Employer','Location','Description','Requirements','Work Type']})}
Return JSON: {{"match_score": <0-100 int>, "reasoning": ["bullet1","bullet2","bullet3"], "summary": "2-3 sentence summary"}}
Weight exact skill matches highest, then partial skill overlap, then career-interest alignment, then location/work-type fit."""
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
    title = (opp.get("Job Title", "") or "").lower()
    text = f"{title} {opp.get('Description','')} {opp.get('Requirements','')}".lower()

    exact_skill_hits, partial_skill_hits = 0, 0
    for s in skills:
        if not s:
            continue
        if re.search(rf"\b{re.escape(s)}\b", text):
            exact_skill_hits += 1
        elif any(tok in text for tok in s.split() if len(tok) > 3):
            partial_skill_hits += 1

    interest_hits = 0
    for i in interests:
        if not i:
            continue
        if i in title:
            interest_hits += 2
        elif i in text:
            interest_hits += 1

    score = min(100, 25 + exact_skill_hits * 12 + partial_skill_hits * 5 + interest_hits * 8)
    reasoning = [
        f"Exact skill matches: {exact_skill_hits}",
        f"Partial skill matches: {partial_skill_hits}",
        f"Career-interest signals: {interest_hits}",
    ]
    return score, reasoning, (
        f"{opp.get('Job Title','This role')} at {opp.get('Employer','the employer')} "
        f"shows {'strong' if score >= 70 else 'moderate' if score >= 50 else 'limited'} alignment with your profile."
    )


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
            risk = data["risk_level"] if data["risk_level"] in ("Low", "Medium", "High") else base_risk
            return risk, data.get("explanations", base_flags)
    except Exception:
        pass
    return base_risk, base_flags


# ---------- Analysis pipeline ----------
def analyze_opportunity(opp, profile, model):
    # Work-pref filter happens before scoring; here we just trust caller.
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


def filter_by_work_pref(opps, work_pref):
    if work_pref == "All":
        return opps
    return [o for o in opps if (o.get("Work Type") or "").strip().lower() == work_pref.lower()]


# ---------- Parsing pasted text ----------
def parse_pasted_text(text):
    def grab(label):
        m = re.search(rf"{label}\s*[:\-]\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
    return {
        "Job Title": grab("Job Title") or grab("Title") or "",
        "Employer": grab("Employer") or grab("Company") or "",
        "Location": grab("Location") or "",
        "Description": grab("Description") or text,
        "Requirements": grab("Requirements") or "",
        "Application Link": grab("Application Link") or grab("Link") or grab("Apply") or "",
        "Source": grab("Source") or "Pasted by user",
        "Deadline": grab("Deadline") or "",
        "Work Type": grab("Work Type") or "On-site",
    }


# ---------- Sample data loader ----------
@st.cache_data
def load_sample_opportunities():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_opportunities.csv")
    try:
        return pd.read_csv(path).fillna("").to_dict(orient="records")
    except Exception:
        return []


# ---------- UI ----------
st.set_page_config(page_title="AI Opportunity Verification Dashboard", page_icon="✅", layout="wide")

for k, v in {
    "profile": None,
    "results": [],
    "show_high_risk": False,
    "pool": [],          # opportunities ready for scoring
    "pasted_draft": None,
}.items():
    st.session_state.setdefault(k, v)

st.title("✅ AI Opportunity Verification & Matching Dashboard")
st.caption("Discover safe, verified employment opportunities — powered by Google Gemini.")

if not get_api_key():
    st.warning(
        "⚠️ **GEMINI_API_KEY not set.** The app runs with rule-based analysis only. "
        "Get a free key at https://aistudio.google.com/app/apikey and set `GEMINI_API_KEY` "
        "as an environment variable or in `.streamlit/secrets.toml`."
    )

tab1, tab2 = st.tabs(["🔍 Find Opportunities", "📊 Analytics"])

with tab1:
    # ============ STEP 1: PROFILE ============
    st.header("Step 1 — Your Profile")
    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name")
            location = st.text_input("Location")
            education = st.selectbox(
                "Highest Education Level",
                ["High School", "Diploma", "Bachelor's", "Master's", "PhD"],
            )
            years = st.number_input("Years of Experience", 0, 50, 1)
        with c2:
            skills = st.multiselect(
                "Skills (start typing to filter)",
                options=SKILLS_OPTIONS,
                help="Pick from the curated list of 50 skills. Type to filter.",
            )
            interests = st.multiselect(
                "Career Interests (start typing to filter)",
                options=INTERESTS_OPTIONS,
                help="Pick from the curated list of 30 career interests. Type to filter.",
            )
            work_pref = st.radio(
                "Work Preference",
                ["All", "Remote", "Hybrid", "On-site"],
                horizontal=True,
                index=0,
                help="Choose 'All' to skip work-type filtering.",
            )
        accessibility = st.text_area("Accessibility Requirements (optional)")
        submitted = st.form_submit_button("Save Profile", type="primary")

    if submitted:
        st.session_state.profile = {
            "name": name, "location": location, "education": education,
            "years": years, "skills": skills, "interests": interests,
            "work_pref": work_pref, "accessibility": accessibility,
        }
        st.success(f"Profile saved for {name or 'you'}.")

    # ============ STEP 2: OPPORTUNITIES ============
    if st.session_state.profile:
        st.header("Step 2 — Add Opportunities")

        # ----- Part A: Sample opportunities -----
        st.subheader("Browse Sample Opportunities")
        sample = load_sample_opportunities()
        st.caption(f"📚 {len(sample)} curated sample opportunities available.")
        df_preview = pd.DataFrame(sample)[["Job Title", "Employer", "Location", "Work Type", "Source", "Deadline"]] if sample else pd.DataFrame()
        if not df_preview.empty:
            st.dataframe(df_preview, use_container_width=True, height=240)
        col_a1, col_a2 = st.columns([1, 3])
        with col_a1:
            include_samples = st.checkbox("Include samples in pool", value=True)

        # ----- Part B: Paste a Job Description -----
        st.subheader("Paste a Job Description")
        pasted = st.text_area(
            "Paste the full text of a job posting below — the app will try to extract fields automatically.",
            height=160,
            key="paste_area",
        )
        if st.button("Parse pasted text"):
            if pasted.strip():
                st.session_state.pasted_draft = parse_pasted_text(pasted)
            else:
                st.info("Paste some text first.")

        if st.session_state.pasted_draft is not None:
            draft = st.session_state.pasted_draft
            missing = [f for f in ["Job Title", "Employer", "Location"] if not draft.get(f)]
            if missing:
                st.warning(f"Could not auto-extract: {', '.join(missing)}. Please fill in below.")
            with st.form("pasted_form"):
                pc1, pc2 = st.columns(2)
                with pc1:
                    draft["Job Title"] = st.text_input("Job Title", draft.get("Job Title", ""))
                    draft["Employer"] = st.text_input("Employer", draft.get("Employer", ""))
                    draft["Location"] = st.text_input("Location", draft.get("Location", ""))
                    draft["Work Type"] = st.selectbox("Work Type", ["On-site", "Remote", "Hybrid"],
                        index=["On-site", "Remote", "Hybrid"].index(draft.get("Work Type", "On-site")) if draft.get("Work Type") in ["On-site", "Remote", "Hybrid"] else 0)
                with pc2:
                    draft["Application Link"] = st.text_input("Application Link", draft.get("Application Link", ""))
                    draft["Source"] = st.text_input("Source", draft.get("Source", "Pasted by user"))
                    draft["Deadline"] = st.text_input("Deadline (YYYY-MM-DD or text)", draft.get("Deadline", ""))
                draft["Description"] = st.text_area("Description", draft.get("Description", ""), height=120)
                draft["Requirements"] = st.text_area("Requirements", draft.get("Requirements", ""), height=100)
                if st.form_submit_button("Add pasted opportunity to pool"):
                    st.session_state.pool.append(dict(draft))
                    st.session_state.pasted_draft = None
                    st.success("Added to pool.")

        # ----- Part C: Manual entry -----
        st.subheader("Add Opportunity Manually")
        with st.form("manual_form", clear_on_submit=True):
            mc1, mc2 = st.columns(2)
            with mc1:
                m_title = st.text_input("Job Title")
                m_employer = st.text_input("Employer")
                m_location = st.text_input("Location")
                m_worktype = st.selectbox("Work Type", ["On-site", "Remote", "Hybrid"])
            with mc2:
                m_link = st.text_input("Application Link")
                m_source = st.text_input("Source")
                m_deadline = st.date_input("Deadline", value=date.today())
            m_desc = st.text_area("Description", height=120)
            m_reqs = st.text_area("Requirements", height=100)
            if st.form_submit_button("Add to pool"):
                if not m_title.strip():
                    st.error("Job Title is required.")
                else:
                    st.session_state.pool.append({
                        "Job Title": m_title, "Employer": m_employer, "Location": m_location,
                        "Description": m_desc, "Requirements": m_reqs,
                        "Application Link": m_link, "Source": m_source or "Manual entry",
                        "Deadline": m_deadline.isoformat() if m_deadline else "",
                        "Work Type": m_worktype,
                    })
                    st.success("Added to pool.")

        # ----- Pool summary + Trusted sources -----
        pool_size = len(st.session_state.pool) + (len(sample) if include_samples else 0)
        st.markdown("---")
        col_p1, col_p2 = st.columns([2, 1])
        with col_p1:
            st.info(f"📦 **{pool_size} opportunities ready for matching** "
                    f"({len(sample) if include_samples else 0} sample + {len(st.session_state.pool)} added by you)")
        with col_p2:
            if st.button("🗑️ Clear added opportunities"):
                st.session_state.pool = []
                st.rerun()

        with st.expander("🌐 Trusted Job Sources (click to expand)", expanded=False):
            st.caption("These job boards are vetted. Open them in a new tab to search directly — the app does not scrape them.")
            tc1, tc2 = st.columns(2)
            with tc1:
                st.markdown("**Local Job Boards**")
                for label, url in LOCAL_JOB_BOARDS:
                    st.markdown(f"- [{label}]({url})")
            with tc2:
                st.markdown("**Remote & International**")
                for label, url in REMOTE_JOB_BOARDS:
                    st.markdown(f"- [{label}]({url})")

        # ----- Analyze -----
        if st.button("🤖 Analyze with AI", type="primary", disabled=pool_size == 0):
            model = get_gemini_model()
            all_opps = (sample if include_samples else []) + st.session_state.pool
            filtered = filter_by_work_pref(all_opps, st.session_state.profile["work_pref"])
            if not filtered:
                st.warning("No opportunities match your work preference. Try changing it to 'All'.")
            else:
                results = []
                prog = st.progress(0.0, text="Scoring opportunities…")
                status = st.empty()
                for i, opp in enumerate(filtered):
                    status.write(f"Analyzing {i+1}/{len(filtered)}: {opp.get('Job Title','')[:60]}")
                    results.append(analyze_opportunity(opp, st.session_state.profile, model))
                    prog.progress((i + 1) / len(filtered), text=f"Scoring {i+1}/{len(filtered)}")
                status.empty()
                prog.empty()
                st.session_state.results = sorted(results, key=lambda r: r["final_score"], reverse=True)
                st.success(f"Analysis complete — {len(results)} opportunities scored.")

    # ============ STEP 3: RESULTS ============
    if st.session_state.results:
        st.header("Step 3 — Ranked Opportunities")
        st.checkbox("Show high-risk opportunities", key="show_high_risk",
                    help="High-risk postings are hidden by default for your safety.")

        with st.expander("ℹ️ What do these scores mean?"):
            st.markdown(
                "- **Match** — how well the role aligns with your skills and interests (0–100).\n"
                "- **QA** — completeness/quality of the posting itself (0–100).\n"
                "- **Trust** — reputation of the source job board (0–100).\n"
                "- **Risk** — likelihood the posting is a scam (Low / Medium / High).\n"
                "- **Final** — weighted blend: 40% Match + 40% QA + 20% Trust. High-risk postings score 0."
            )

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
                    f"<p style='margin:2px 0;color:#555'>{r['opp'].get('Employer','')} · "
                    f"{r['opp'].get('Location','')} · {r['opp'].get('Work Type','')}</p>"
                    f"</div>", unsafe_allow_html=True)
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Match", r["match_score"], help="Fit with your skills + interests")
                c2.metric("QA", r["qa_score"], help="Posting completeness")
                c3.metric("Trust", r["trust_score"], help="Source reputation")
                c4.metric("Risk", r["risk"], help="Scam likelihood")
                c5.metric("Final", r["final_score"], help="40% Match + 40% QA + 20% Trust")
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
