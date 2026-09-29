import os, json
from itertools import product
import pandas as pd
import streamlit as st

st.set_page_config(page_title="FlowMate — AI Design Companion", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

SYSTEM_PROMPT = '''You are FlowMate, an AI design companion for product designers.
Transform messy product notes into multiple actionable UX directions while keeping the human designer in control.
Return ONLY valid JSON with keys: user_problem, user_needs, user_goal, recommended_flow, layout_directions, ui_copy, usability_risks, questions_for_designer.
layout_directions must contain exactly 3 objects with title, rationale, key_elements, tradeoff.
ui_copy objects: element, copy. usability_risks objects: risk, why_it_matters, mitigation.
Principles: start from user needs; offer alternatives, not one correct design; concise natural copy; do not invent research; consider accessibility, trust, cognitive load, error recovery and edge cases; state assumptions/questions when notes are incomplete.
For Careem product contexts, make concepts feel native to a consumer mobile app: use clear mobile hierarchy, white or soft-neutral surfaces, charcoal text, restrained Careem-green accents, concise status and ETA, and easy-to-find help. Respect the brand without inventing official components, policies, or research. Keep the three directions meaningfully distinct.'''

DEMO = {
  "user_problem": "Users are uncertain about what is happening with their food order and repeatedly reopen tracking because the current status does not clearly explain progress or delivery timing.",
  "user_needs": ["Know the current stage at a glance.", "Understand when the order is likely to arrive.", "Know what to do if the order is delayed."],
  "user_goal": "Check order status quickly and feel confident that the order is progressing.",
  "recommended_flow": ["Order confirmed", "Restaurant preparing", "Courier assigned", "Courier picked up", "Courier arriving", "Delivered"],
  "layout_directions": [
    {"title":"Timeline-first", "rationale":"Makes progress immediately scannable and answers the primary question: what is happening now?", "key_elements":["Current status","Next milestone","ETA range","Delay explanation"], "tradeoff":"Less geographic context than a map."},
    {"title":"Map-first", "rationale":"Useful when courier location becomes the most meaningful signal after pickup.", "key_elements":["Live map","Courier marker","ETA range","Compact status label"], "tradeoff":"A map can dominate before location is useful."},
    {"title":"ETA-first", "rationale":"Puts the most decision-relevant information first for users who mainly want to know when food will arrive.", "key_elements":["Arrival range","Current stage","Progress indicator","Help/delay action"], "tradeoff":"Can hide operational context if the status is too compressed."}
  ],
  "ui_copy": [
    {"element":"Current status","copy":"Your order is being prepared"},
    {"element":"ETA","copy":"Estimated arrival · 7:35–7:45 PM"},
    {"element":"Delay state","copy":"Running a little late · We’ll keep you updated"},
    {"element":"Support action","copy":"Need help with your order?"}
  ],
  "usability_risks": [
    {"risk":"False precision","why_it_matters":"An exact ETA can feel like a promise and damage trust when conditions change.","mitigation":"Prefer an arrival range and update it when confidence changes."},
    {"risk":"Status ambiguity","why_it_matters":"A label such as 'In progress' does not tell users what is actually happening.","mitigation":"Use plain-language operational states with a clear current step."},
    {"risk":"Poor delay recovery","why_it_matters":"A delayed order can turn uncertainty into repeated support contacts.","mitigation":"Explain the delay and surface a relevant next action."}
  ],
  "questions_for_designer": ["At which stage do users most often contact support?", "How accurate is the current ETA at each delivery stage?", "What actions are available when an order is delayed?"]
}

DUMMY_FEATURES = (
    "Careem Food order tracking",
    "Careem ride pickup",
    "Schedule a Careem ride",
    "Careem airport transfer",
    "Careem Grocery substitutions",
    "Careem Pay bill payment",
    "Careem wallet top-up",
    "Careem Plus subscription",
    "Careem Box parcel delivery",
    "Careem ride cancellation and refund",
)
DUMMY_CONTEXTS = (
    "new to the service and needs reassurance before confirming",
    "using the app with limited connectivity",
    "in a hurry and needs the next action at a glance",
    "using a screen reader or enlarged text",
    "recovering from a previous failed attempt",
)
DUMMY_FRICTIONS = (
    ("Unclear progress", "The current status does not make the next step clear, so the customer checks again."),
    ("Hard-to-find action", "A key action is hard to find without scanning several parts of the screen."),
    ("Uncertain change", "Timing or price changes are not explained, which weakens confidence."),
    ("Unclear recovery", "The customer cannot tell whether to wait, retry, or contact support."),
)


def build_dummy_dataset():
    records = []
    for record_number, (feature, context, friction) in enumerate(
        product(DUMMY_FEATURES, DUMMY_CONTEXTS, DUMMY_FRICTIONS), start=1
    ):
        theme, observation = friction
        records.append({
            "record_id": f"FM-{record_number:03d}",
            "feature": feature,
            "context": context,
            "friction_theme": theme,
            "notes": f"Synthetic scenario: A customer using {feature} is {context}. {observation}",
        })
    return records


DUMMY_DATASET = build_dummy_dataset()
DUMMY_RECORDS_BY_ID = {record["record_id"]: record for record in DUMMY_DATASET}

CSS = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: Inter, sans-serif; }
.stApp { background: #f7f8f7; color:#171b18; }
.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
.hero { background: #101412; color: white; border-radius: 24px; padding: 30px 34px; margin-bottom: 22px; position: relative; overflow: hidden; }
.hero:after { content:''; position:absolute; width:260px; height:260px; right:-80px; top:-110px; border-radius:50%; background:rgba(0,179,125,.16); }
.logo { display:flex; align-items:center; gap:10px; font-size:14px; font-weight:700; letter-spacing:.2px; opacity:.9; }
.logo-mark { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; background:#00b37d; color:#101412; font-weight:900; }
.hero h1 { font-size: 34px; line-height:1.1; margin:22px 0 10px; letter-spacing:-1.2px; }
.hero p { color:#c7ceca; max-width:720px; margin:0; font-size:15px; line-height:1.65; }
.pill { display:inline-block; margin-top:18px; padding:7px 11px; border-radius:999px; background:#1c241f; color:#cfe8c1; font-size:12px; font-weight:600; }
.section { margin: 26px 0 12px; }
.eyebrow { font-size:11px; text-transform:uppercase; letter-spacing:1.2px; font-weight:800; color:#727b75; }
.section h2 { font-size:22px; letter-spacing:-.4px; margin:5px 0 3px; color:#171b18; }
.section-sub { color:#6d756f; font-size:13px; margin-bottom:14px; }
.card { background:white; border:1px solid #e7eae7; border-radius:18px; padding:19px; box-shadow:0 2px 10px rgba(16,20,18,.035); height:100%; color:#171b18; }
.card h3 { font-size:15px; margin:0 0 8px; color:#171b18; }
.card p { font-size:13px; line-height:1.55; color:#505952; }
.problem { border-left:4px solid #00b37d; }
.goal { background:#eaf6ef; border-color:#d4eadc; }
.chip { display:inline-block; padding:6px 9px; border-radius:9px; background:#f1f3f1; margin:4px 4px 0 0; font-size:11px; color:#424a45; }
.flow { display:flex; gap:7px; align-items:center; overflow-x:auto; padding:4px 0 9px; }
.step { min-width:145px; background:white; border:1px solid #e7eae7; border-radius:13px; padding:12px; color:#171b18; }
.step-num { font-size:10px; color:#68716b; font-weight:800; }
.step-name { font-size:12px; font-weight:700; margin-top:4px; color:#171b18; }
.arrow { color:#68716b; font-size:17px; }
.direction { border-top:3px solid #dfe5df; }
.direction:hover { border-top-color:#00b37d; }
.direction-num { font-size:10px; font-weight:800; color:#879089; }
.tradeoff { background:#f7f8f7; padding:9px; border-radius:9px; font-size:11px; color:#68716b; margin-top:10px; }
.wireframe { background:#111512; border-radius:18px; padding:16px; color:white; min-height:255px; }
.phone { background:#f6f7f5; border-radius:15px; padding:12px; color:#151915; }
.phone-top { display:flex; justify-content:space-between; font-size:9px; color:#777f79; }
.eta { font-size:22px; font-weight:800; margin:10px 0 2px; }
.status { font-size:11px; color:#5e675f; }
.progress { display:flex; align-items:center; margin:15px 0; }
.dot { width:11px; height:11px; border-radius:50%; background:#00b37d; }
.line { height:2px; background:#dfe4df; flex:1; }
.copy-row { padding:11px 0; border-bottom:1px solid #eceeec; }
.copy-label { font-size:10px; color:#68716b; text-transform:uppercase; letter-spacing:.7px; font-weight:800; }
.copy-text { font-size:13px; font-weight:600; margin-top:3px; color:#171b18; }
.risk { padding:13px 0; border-bottom:1px solid #eceeec; }
.risk:last-child { border-bottom:0; }
.risk-title { font-weight:700; font-size:13px; color:#171b18; }
.risk-body { color:#505952; font-size:11px; line-height:1.5; margin-top:3px; }
.footer { color:#68716b; font-size:11px; text-align:center; padding-top:28px; }
.preview-item { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid rgba(255,255,255,.12); font-size:12px; }
.preview-item:last-child { border-bottom:0; }
.preview-index { color:#526d20; font-size:10px; font-weight:800; }
[data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] { color:#505952 !important; }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color:#171b18 !important; }
[data-testid="stRadio"] label, [data-testid="stRadio"] label * { color:#171b18 !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div > div { min-height:46px; background:#fff !important; border:1px solid #cbd3cc !important; border-radius:11px !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] * { color:#171b18 !important; }
[data-testid="stSelectbox"] [role="combobox"] { background:#fff !important; color:#171b18 !important; -webkit-text-fill-color:#171b18 !important; }
[data-baseweb="popover"] ul { background:#fff !important; }
[data-baseweb="popover"] li { color:#171b18 !important; }
[data-baseweb="popover"] li:hover { background:#eaf6ef !important; }
[data-testid="stSelectbox"]:focus-within [data-baseweb="select"] > div { border-color:#00b37d !important; box-shadow:0 0 0 1px #00b37d !important; }
[data-testid="stDownloadButton"] button { background:#00b37d !important; border:0 !important; border-radius:11px !important; color:#10231b !important; -webkit-text-fill-color:#10231b !important; font-weight:700 !important; }
[data-testid="stDownloadButton"] button * { color:#10231b !important; -webkit-text-fill-color:#10231b !important; }
[data-testid="stDownloadButton"] button:hover { background:#009b6b !important; color:#fff !important; -webkit-text-fill-color:#fff !important; }
[data-testid="stDownloadButton"] button:hover * { color:#fff !important; -webkit-text-fill-color:#fff !important; }
.note-preview { margin-top:8px; padding:14px 16px; border:1px solid #d4eadc; border-radius:11px; background:#f2f8f4; color:#171b18; }
.note-preview-label { color:#526d20; font-size:10px; font-weight:800; text-transform:uppercase; }
.note-preview p { margin:6px 0 0; color:#38443c; font-size:13px; line-height:1.55; }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { border-radius:12px; border:1px solid #dfe4df; background:white; color:#171b18 !important; -webkit-text-fill-color:#171b18; caret-color:#171b18; }
[data-testid="stTextArea"] textarea::placeholder, [data-testid="stTextInput"] input::placeholder { color:#68716b !important; opacity:1; -webkit-text-fill-color:#68716b; }
button[kind="primary"] { border-radius:11px !important; background:#00b37d !important; border:0 !important; color:#10231b !important; font-weight:700 !important; }
button[kind="primary"]:hover { background:#009b6b !important; color:#fff !important; }
[data-testid="stSidebar"] { background:#101412; }
@media (max-width: 700px) {
    .block-container { padding:1rem 1rem 2.5rem; }
    .hero { padding:22px; border-radius:16px; }
    .hero h1 { font-size:28px; }
    .section { margin-top:22px; }
    .card { padding:15px; border-radius:12px; }
    .flow { padding-bottom:12px; }
    .step { min-width:125px; }
    [data-testid="stRadio"] [role="radiogroup"] { gap:8px; flex-wrap:wrap; }
}
</style>
'''
st.markdown(CSS, unsafe_allow_html=True)


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end+1])


def get_groq_api_key():
    try:
        secrets_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        secrets_key = ""
    return secrets_key or os.environ.get("GROQ_API_KEY", "")


def get_groq_model():
    try:
        secrets_model = st.secrets.get("GROQ_MODEL", "")
    except Exception:
        secrets_model = ""
    return secrets_model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def generate_with_groq(notes, context, feature):
    try:
        from groq import Groq
        client = Groq(api_key=get_groq_api_key())
        prompt = f"FEATURE: {feature}\nPRODUCT CONTEXT: {context}\n\nDESIGN NOTES:\n{notes}"
        response = client.chat.completions.create(
            model=get_groq_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return extract_json(response.choices[0].message.content), None
    except Exception as e:
        error_message = str(e)
        api_key = get_groq_api_key()
        if api_key:
            error_message = error_message.replace(api_key, "[redacted API key]")
        status_code = getattr(e, "status_code", None)
        guidance = {
            401: "Groq rejected the API key. Revoke the exposed key and add a new key to .streamlit/secrets.toml.",
            403: "This key or account does not have access to the requested model.",
            404: "The requested model was not found. Check the configured Groq model name.",
            429: "Groq rate limit or quota reached. Check your Groq console and retry later.",
        }.get(status_code, "Check the status and message below, then verify the Groq key, model access, and network connection.")
        status_text = f"HTTP {status_code}" if status_code else type(e).__name__
        detail_text = error_message or repr(e)
        return None, f"{guidance}\n\n{status_text}: {detail_text}"

# Hero
st.markdown('''<div class="hero">
<div class="logo"><span class="logo-mark">✦</span> FLOWMATE <span style="opacity:.5">/</span> AI DESIGN COMPANION</div>
<h1>From messy notes<br>to meaningful UX directions.</h1>
<p>A human-in-the-loop design copilot for shaping clear, trustworthy Careem Food experiences from research observations and feature ideas.</p>
<div class="pill">CAREEM FOOD CONCEPT · AI proposes, designer decides</div>
</div>''', unsafe_allow_html=True)

# Input workspace
st.markdown('<div class="section"><div class="eyebrow">01 · Frame the problem</div><h2>Give FlowMate the messy version.</h2><div class="section-sub">Rough notes are enough. The AI will structure the problem before suggesting interface directions.</div></div>', unsafe_allow_html=True)
# st.caption("Reference dataset: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). This prototype uses its own synthetic Careem scenario records; no file upload is needed.")

c1, c2 = st.columns([1, 1])
with c1:
    feature = st.selectbox("Product / feature", DUMMY_FEATURES, key="feature_input")
with c2:
    context = st.selectbox("Customer context", DUMMY_CONTEXTS, key="context_input")
selected_record_id = st.selectbox(
    "Scenario note · 200 synthetic records",
    [record["record_id"] for record in DUMMY_DATASET],
    format_func=lambda record_id: (
        f"{record_id} · {DUMMY_RECORDS_BY_ID[record_id]['feature']} · "
        f"{DUMMY_RECORDS_BY_ID[record_id]['friction_theme']}"
    ),
    key="notes_input",
)
notes = DUMMY_RECORDS_BY_ID[selected_record_id]["notes"]
st.markdown(
    f'<div class="note-preview"><div class="note-preview-label">Selected synthetic note · {selected_record_id}</div><p>{notes}</p></div>',
    unsafe_allow_html=True,
)
download_col, note_col = st.columns([1, 4])
with download_col:
    st.download_button(
        "Download 200 records",
        data=pd.DataFrame(DUMMY_DATASET).to_csv(index=False).encode("utf-8"),
        file_name="flowmate_careem_dummy_dataset.csv",
        mime="text/csv",
    )
with note_col:
    st.caption("All 200 records are fictional. Mix any feature, context, and note to explore different combinations.")

b1, b2 = st.columns([1, 5])
with b1:
    generate = st.button("✦  Explore directions", type="primary", use_container_width=True)
with b2:
    st.caption("Try replacing the example with your own feature idea, interview notes or support feedback.")

if "result" not in st.session_state:
    st.session_state.result = DEMO
    st.session_state.demo = True
if generate:
    if not notes.strip():
        st.warning("Add a few design notes first.")
    elif get_groq_api_key():
        with st.spinner("Exploring user needs and alternative directions…"):
            result, error = generate_with_groq(notes, context, feature)
        if result:
            st.session_state.result = result
            st.session_state.demo = False
        else:
            st.error("The Groq request failed. Showing the example output instead.")
            with st.expander("Groq error details", expanded=True):
                st.code(error)
                st.caption("Check your Groq key in .streamlit/secrets.toml, account access, and model availability.")
            st.session_state.result = DEMO
            st.session_state.demo = True
    else:
        st.info("Demo mode — add GROQ_API_KEY to enable live generation.")
        st.session_state.result = DEMO
        st.session_state.demo = True

r = st.session_state.result
mode = "Demo output · curated dummy scenario" if st.session_state.demo else "Live AI output · validate before shipping"
st.markdown(f'<div style="margin:18px 0 4px;color:#727b75;font-size:11px;font-weight:700;letter-spacing:.6px">{mode.upper()}</div>', unsafe_allow_html=True)

# Understand
st.markdown('<div class="section"><div class="eyebrow">02 · Understand</div><h2>What are we actually solving?</h2></div>', unsafe_allow_html=True)
a, b = st.columns([1.65, 1])
with a:
    st.markdown(f'<div class="card problem"><h3>Core user problem</h3><p>{r["user_problem"]}</p></div>', unsafe_allow_html=True)
with b:
    st.markdown(f'<div class="card goal"><h3>User goal</h3><p>{r["user_goal"]}</p></div>', unsafe_allow_html=True)

st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
needs_html = ''.join([f'<span class="chip">{x}</span>' for x in r['user_needs']])
st.markdown(f'<div class="card"><h3>User needs</h3>{needs_html}</div>', unsafe_allow_html=True)

# Explore
st.markdown('<div class="section"><div class="eyebrow">03 · Explore</div><h2>Three directions, not one answer.</h2><div class="section-sub">Each direction makes a different product trade-off explicit.</div></div>', unsafe_allow_html=True)
flow_html = '<div class="flow">'
for i, x in enumerate(r['recommended_flow']):
    flow_html += f'<div class="step"><div class="step-num">0{i+1}</div><div class="step-name">{x}</div></div>'
    if i < len(r['recommended_flow']) - 1: flow_html += '<div class="arrow">→</div>'
flow_html += '</div>'
st.markdown(flow_html, unsafe_allow_html=True)

cols = st.columns(3)
for i, (col, d) in enumerate(zip(cols, r['layout_directions'][:3]), 1):
    with col:
        chips = ''.join([f'<span class="chip">{x}</span>' for x in d['key_elements']])
        st.markdown(f'''<div class="card direction"><div class="direction-num">DIRECTION 0{i}</div><h3 style="margin-top:7px">{d['title']}</h3><p>{d['rationale']}</p><div>{chips}</div><div class="tradeoff"><b>Trade-off</b><br>{d['tradeoff']}</div></div>''', unsafe_allow_html=True)

direction_options = r['layout_directions'][:3]
selected_title = st.radio(
    "Preview a direction",
    [direction['title'] for direction in direction_options],
    horizontal=True,
    key="direction_preview",
)
selected_direction = next(direction for direction in direction_options if direction['title'] == selected_title)

# Mini wireframe
st.markdown('<div class="section"><div class="eyebrow">04 · Make it tangible</div><h2>Explore a direction</h2><div class="section-sub">Select an option above to inspect its key elements and trade-off. The alternatives are prompts for critique, not a ranked recommendation.</div></div>', unsafe_allow_html=True)
w1, w2 = st.columns([1, 1.45])
with w1:
    elements_html = ''.join(
        f'<div class="preview-item"><span class="preview-index">0{index}</span><span>{element}</span></div>'
        for index, element in enumerate(selected_direction['key_elements'], 1)
    )
    st.markdown(f'''<div class="wireframe"><div style="font-size:10px;opacity:.6;margin-bottom:9px">DIRECTION PREVIEW</div><div class="phone"><div class="phone-top"><span>Concept structure</span><span>•••</span></div><div class="eta" style="font-size:18px">{selected_direction['title']}</div><div class="status">Key interface elements</div>{elements_html}</div></div>''', unsafe_allow_html=True)
with w2:
    st.markdown(f'''<div class="card"><h3>{selected_direction['title']}</h3><p>{selected_direction['rationale']}</p><div class="eyebrow" style="margin-top:20px">Trade-off</div><p style="margin-top:5px">{selected_direction['tradeoff']}</p><div class="eyebrow" style="margin-top:18px">Designer decides</div><p style="margin-top:5px"><b>Use this direction as a discussion starter; validate it against user evidence and product constraints.</b></p></div>''', unsafe_allow_html=True)

# Make usable
st.markdown('<div class="section"><div class="eyebrow">05 · Make it usable</div><h2>Copy, risks and open questions.</h2></div>', unsafe_allow_html=True)
u1, u2 = st.columns([1, 1])
with u1:
    copy_html = '<div class="card"><h3>Suggested UI copy</h3>'
    for item in r['ui_copy']:
        copy_html += f'<div class="copy-row"><div class="copy-label">{item["element"]}</div><div class="copy-text">{item["copy"]}</div></div>'
    copy_html += '</div>'
    st.markdown(copy_html, unsafe_allow_html=True)
with u2:
    risk_html = '<div class="card"><h3>Usability risks</h3>'
    for item in r['usability_risks']:
        risk_html += f'<div class="risk"><div class="risk-title">{item["risk"]}</div><div class="risk-body">{item["why_it_matters"]}</div><div class="risk-body"><b>Mitigation:</b> {item["mitigation"]}</div></div>'
    risk_html += '</div>'
    st.markdown(risk_html, unsafe_allow_html=True)

q_html = '<div class="card" style="margin-top:12px"><h3>Questions for the designer</h3>'
for i, q in enumerate(r['questions_for_designer'], 1):
    q_html += f'<div class="copy-row"><span style="color:#929a94;font-size:11px;font-weight:800">0{i}</span>&nbsp;&nbsp;{q}</div>'
q_html += '</div>'
st.markdown(q_html, unsafe_allow_html=True)

st.markdown('<div class="footer">FlowMate is a design exploration prototype. AI output should be validated with research, product constraints, accessibility and technical feasibility before implementation.</div>', unsafe_allow_html=True)
