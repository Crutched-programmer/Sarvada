import streamlit as st
import requests
import time
import pandas as pd
import base64
import io
import json
import re

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sarvam Agent",
    page_icon="🦆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SESSION STATE DEFAULTS ────────────────────────────────────────────────────
defaults = {
    "messages":           [],
    "total_messages":     0,
    "token_history":      [],
    "favourites":         [],
    "tts_audio":          None,
    "stt_result":         "",
    "show_settings":      False,
    "accent":             "#db5151",
    "cli_mode":           False,
    "memory_summary":     "",
    "last_summarised":    0,
    "search_query":       "",
    "translate_results":  {},
    "msg_translations":   {},
    "show_tr_picker":     {},
    # ── Feature 10: Multiple Chat Sessions ──
    "sessions":           {},          # {session_id: {name, messages, token_history, memory_summary, last_summarised}}
    "active_session":     None,        # current session id
    "session_counter":    0,           # auto-increment for new session ids
    # ── Feature 16: Inline command state ──
    "cmd_result":         None,
    # ── v2 nav ──
    "active_tab":    "chat",
    "nav_collapsed": False,
    "api_key":       "",
    "light_mode":    False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── FEATURE 10: SESSION HELPERS ───────────────────────────────────────────────
def new_session(name=None):
    sid = st.session_state.session_counter + 1
    st.session_state.session_counter = sid
    sname = name or f"Chat {sid}"
    st.session_state.sessions[sid] = {
        "name":            sname,
        "messages":        [],
        "token_history":   [],
        "memory_summary":  "",
        "last_summarised": 0,
        "total_messages":  0,
    }
    return sid

def switch_session(sid):
    """Save current session state then load the target session."""
    cur = st.session_state.active_session
    if cur and cur in st.session_state.sessions:
        st.session_state.sessions[cur]["messages"]        = st.session_state.messages
        st.session_state.sessions[cur]["token_history"]   = st.session_state.token_history
        st.session_state.sessions[cur]["memory_summary"]  = st.session_state.memory_summary
        st.session_state.sessions[cur]["last_summarised"] = st.session_state.last_summarised
        st.session_state.sessions[cur]["total_messages"]  = st.session_state.total_messages

    st.session_state.active_session   = sid
    sess = st.session_state.sessions[sid]
    st.session_state.messages         = sess["messages"]
    st.session_state.token_history    = sess["token_history"]
    st.session_state.memory_summary   = sess["memory_summary"]
    st.session_state.last_summarised  = sess["last_summarised"]
    st.session_state.total_messages   = sess["total_messages"]
    st.session_state.msg_translations = {}
    st.session_state.show_tr_picker   = {}
    st.session_state.cmd_result       = None

def save_current_session():
    cur = st.session_state.active_session
    if cur and cur in st.session_state.sessions:
        st.session_state.sessions[cur]["messages"]        = st.session_state.messages
        st.session_state.sessions[cur]["token_history"]   = st.session_state.token_history
        st.session_state.sessions[cur]["memory_summary"]  = st.session_state.memory_summary
        st.session_state.sessions[cur]["last_summarised"] = st.session_state.last_summarised
        st.session_state.sessions[cur]["total_messages"]  = st.session_state.total_messages

# Initialise a default session on first run
if st.session_state.active_session is None:
    first_sid = new_session("Chat 1")
    st.session_state.active_session = first_sid

# ─── ACCENT COLOUR HELPERS ─────────────────────────────────────────────────────
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def darken(h, factor=0.85):
    r, g, b = hex_to_rgb(h)
    return "#{:02x}{:02x}{:02x}".format(int(r*factor), int(g*factor), int(b*factor))

def lighten(h, factor=1.25):
    r, g, b = hex_to_rgb(h)
    return "#{:02x}{:02x}{:02x}".format(min(255,int(r*factor)), min(255,int(g*factor)), min(255,int(b*factor)))

def alpha(h, a):
    r, g, b = hex_to_rgb(h)
    return f"rgba({r},{g},{b},{a})"

def tint_bg(h, mix=0.08):
    r, g, b = hex_to_rgb(h)
    return "#{:02x}{:02x}{:02x}".format(int(r*mix), int(g*mix), int(b*mix))

A   = st.session_state.accent
AD  = darken(A)
AL  = lighten(A)
AT  = tint_bg(A, 0.12)
AT2 = tint_bg(A, 0.18)

CLI = st.session_state.cli_mode

# ─── DYNAMIC CSS ───────────────────────────────────────────────────────────────
FONT         = "'Courier New', monospace" if CLI else "'IBM Plex Mono', monospace"
MSG_RADIUS   = "4px"  if CLI else "24px"
BTN_RADIUS   = "4px"  if CLI else "8px"
INPUT_RADIUS = "4px"  if CLI else "8px"

# ── Theme variables ───────────────────────────────────────────────────────────
_LM = st.session_state.get("light_mode", False)
BG       = "#f4f4f8"        if _LM else "#080810"
SURFACE  = "#ffffff"        if _LM else "#111118"
SURFACE2 = "#f0f0f5"        if _LM else "#0d0d14"
BORDER   = "rgba(0,0,0,0.10)"   if _LM else "rgba(255,255,255,0.09)"
TXT      = "#111120"        if _LM else "#dddde8"
TXT2     = "#666677"        if _LM else "rgba(255,255,255,0.4)"
SB_BG    = "#fafafa"        if _LM else "#0b0b14"
SB_BDR   = "rgba(0,0,0,0.10)"   if _LM else alpha(A,0.25)
PLACEHOLDER = alpha(A,0.45) if _LM else alpha(A,0.4)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

*, html, body, [class*="css"] {{ font-family:{FONT}!important; box-sizing:border-box; }}
.stApp, .main, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"] {{ background:{BG}!important; }}
.block-container {{ padding-top:1rem!important; max-width:860px!important; }}
#MainMenu,footer,header {{ visibility:hidden; }}

/* ══ SIDEBAR ════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {{
    background:{SB_BG}!important;
    border-right:1px solid {SB_BDR}!important;
    min-width:{"46px" if st.session_state.nav_collapsed else "200px"}!important;
    max-width:{"46px" if st.session_state.nav_collapsed else "200px"}!important;
    transition:min-width 0.18s ease,max-width 0.18s ease!important;
    overflow:hidden!important; transform:none!important; visibility:visible!important;
}}
section[data-testid="stSidebar"] > div:first-child {{
    padding:0!important; overflow-x:hidden!important;
    display:flex!important; flex-direction:column!important;
    height:100vh!important;
}}
/* bottom-pinned items use position fixed */
.sb-bottom {{
    position:fixed!important;
    bottom:0!important;
    width:{"46px" if st.session_state.nav_collapsed else "200px"}!important;
    background:{SB_BG}!important;
    border-top:1px solid {SB_BDR}!important;
    z-index:10!important;
}}
[data-testid="stSidebarCollapseButton"],[data-testid="collapsedControl"] {{ display:none!important; }}

/* nav buttons — zero padding, zero chrome */
section[data-testid="stSidebar"] button {{
    all:unset!important;
    display:flex!important; align-items:center!important;
    width:100%!important; cursor:pointer!important;
    padding:0!important; margin:0!important;
    justify-content:{"center" if st.session_state.nav_collapsed else "flex-start"}!important;
    font-family:{FONT}!important;
    font-size:{"17px" if st.session_state.nav_collapsed else "12px"}!important;
    color:{A}!important;
    white-space:nowrap!important; overflow:hidden!important;
    transition:color 0.1s,background 0.1s!important;
    line-height:2.2!important;
    min-height:0!important; height:auto!important;
    border-radius:0!important;
    gap:9px!important;
    padding-left:{"0" if st.session_state.nav_collapsed else "14px"}!important;
}}
section[data-testid="stSidebar"] button:hover {{
    color:{AL}!important;
    background:{"rgba(0,0,0,0.04)" if _LM else alpha(A,0.07)}!important;
}}
section[data-testid="stSidebar"] .nav-active button {{
    color:{A}!important;
    background:{"rgba(0,0,0,0.06)" if _LM else alpha(A,0.11)}!important;
    border-left:2px solid {A}!important;
    padding-left:{"0" if st.session_state.nav_collapsed else "12px"}!important;
    font-weight:600!important;
}}
/* collapse toggle at bottom */
section[data-testid="stSidebar"] .nav-collapse button {{
    font-size:13px!important;
    color:{TXT2}!important;
    border-top:1px solid {SB_BDR}!important;
    justify-content:center!important;
    padding:0!important;
    line-height:2.8!important;
}}
section[data-testid="stSidebar"] .nav-collapse button:hover {{
    color:{A}!important; background:transparent!important;
}}
section[data-testid="stSidebar"] * {{ color:{TXT2}!important; }}
section[data-testid="stSidebar"] hr {{ border-color:{BORDER}!important; margin:3px 0!important; }}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {{
    color:{A}!important; font-size:1.05rem!important; font-weight:600!important;
}}
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
    color:{alpha(A,0.55)}!important; font-size:9px!important;
}}
section[data-testid="stSidebar"] input {{
    background:{"rgba(0,0,0,0.05)" if _LM else "rgba(255,255,255,0.05)"}!important;
    border:1px solid {BORDER}!important; color:{TXT}!important;
    border-radius:5px!important; font-size:11px!important; padding:4px 8px!important;
}}
section[data-testid="stSidebar"] .stDownloadButton button {{
    color:{alpha(A,0.6)}!important; font-size:11px!important;
    padding:4px 14px!important; border:1px solid {alpha(A,0.22)}!important;
    border-radius:5px!important; margin:1px 8px!important;
    width:calc(100% - 16px)!important;
    justify-content:center!important; line-height:1.8!important;
}}
section[data-testid="stSidebar"] .stDownloadButton button:hover {{
    color:{AL}!important; border-color:{A}!important;
    background:{alpha(A,0.07)}!important;
}}

/* ══ GLOBAL TEXT ═════════════════════════════════════════════════ */
p,span,li,td,th {{ color:{TXT}!important; }}
h1,h2,h3 {{ color:{TXT}!important; font-weight:500!important; }}
h4 {{ color:{A}!important; }}
label {{ color:{TXT2}!important; font-size:11px!important; }}
div {{ color:{TXT}!important; }}

/* ══ INPUTS ══════════════════════════════════════════════════════ */
input,textarea {{
    background:{SURFACE}!important;
    border:1px solid {alpha(A,0.22)}!important;
    color:{TXT}!important; border-radius:{INPUT_RADIUS}!important;
    transition:border-color 0.15s,box-shadow 0.15s!important;
}}
input:focus,textarea:focus {{
    border-color:{A}!important;
    box-shadow:0 0 0 3px {alpha(A,0.13)}!important;
    outline:none!important; background:{SURFACE}!important;
}}
input::placeholder,textarea::placeholder {{ color:{PLACEHOLDER}!important; }}

/* ══ BUTTONS ══════════════════════════════════════════════════════ */
.stButton>button {{
    background:{SURFACE}!important;
    border:1px solid {alpha(A,0.3)}!important;
    color:{alpha(A,0.85)}!important; border-radius:{BTN_RADIUS}!important;
    font-size:11px!important; letter-spacing:0.03em!important;
    transition:all 0.13s!important; padding:5px 13px!important;
    box-shadow:none!important; transform:none!important;
}}
.stButton>button:hover {{
    background:{alpha(A,0.09) if not _LM else alpha(A,0.08)}!important;
    border-color:{A}!important; color:{AL}!important;
    box-shadow:none!important; transform:none!important;
}}
.stButton>button:active {{ transform:none!important; box-shadow:none!important; }}
.stDownloadButton>button {{
    background:{SURFACE}!important; border:1px solid {alpha(A,0.25)}!important;
    color:{alpha(A,0.7)}!important; border-radius:{BTN_RADIUS}!important;
    font-size:11px!important; transition:all 0.13s!important;
}}
.stDownloadButton>button:hover {{
    background:{alpha(A,0.08)}!important; border-color:{A}!important; color:{AL}!important;
}}

/* ══ SELECTBOX ════════════════════════════════════════════════════ */
[data-testid="stSelectbox"]>div>div {{
    background:{SURFACE}!important; border:1px solid {alpha(A,0.22)}!important;
    border-radius:{BTN_RADIUS}!important; color:{TXT}!important;
}}
[data-testid="stSelectbox"]>div>div:hover {{ border-color:{A}!important; }}
/* dropdown options background */
[data-baseweb="popover"] ul, [data-baseweb="menu"] {{
    background:{SURFACE}!important; border:1px solid {BORDER}!important;
}}
[data-baseweb="menu"] li {{ color:{TXT}!important; }}
[data-baseweb="menu"] li:hover {{ background:{alpha(A,0.08)}!important; }}

/* ══ SLIDERS — white ══════════════════════════════════════════════ */
[data-testid="stSlider"] [role="slider"] {{
    background:#ffffff!important; border:2px solid rgba(255,255,255,0.7)!important;
    box-shadow:0 1px 4px rgba(0,0,0,0.3)!important;
}}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"] {{ color:{TXT2}!important; }}
div[data-baseweb="slider"]>div>div>div {{ background:#ffffff!important; }}
[data-testid="stSlider"]>div>div>div:first-child {{ background:{BORDER}!important; }}

/* ══ TOGGLES — white ══════════════════════════════════════════════ */
[data-testid="stToggle"] label {{ color:{TXT2}!important; }}
div[role="switch"][aria-checked="true"],
[data-testid="stToggle"] div[data-checked="true"] {{
    background-color:#ffffff!important;
}}
[data-testid="stToggle"] input:checked+div,
[data-testid="stToggle"] input:checked~div[role="switch"] {{
    background:#ffffff!important;
}}

/* ══ EXPANDER ══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {{
    background:{SURFACE}!important; border:1px solid {BORDER}!important;
    border-radius:{"4px" if CLI else "10px"}!important;
}}
[data-testid="stExpander"] summary {{ color:{TXT2}!important; }}
[data-testid="stExpander"] summary:hover {{ color:{A}!important; }}

/* ══ METRICS ═══════════════════════════════════════════════════════ */
[data-testid="stMetric"] {{
    background:{SURFACE}!important; border:1px solid {BORDER}!important;
    border-radius:{"4px" if CLI else "10px"}!important; padding:12px 14px!important;
}}
[data-testid="stMetric"]:hover {{ border-color:{alpha(A,0.45)}!important; }}
[data-testid="stMetricValue"] {{ color:{A}!important; font-size:1.3rem!important; font-weight:600!important; }}
[data-testid="stMetricLabel"] {{ color:{alpha(A,0.55)}!important; font-size:10px!important; }}

hr {{ border-color:{BORDER}!important; opacity:1!important; }}

/* ══ BAR CHART / CHART backgrounds ════════════════════════════════ */
[data-testid="stVegaLiteChart"],
[data-testid="stVegaLiteChart"] canvas,
[data-testid="stVegaLiteChart"]>div,
.vega-embed {{ background:{SURFACE}!important; border-radius:8px!important; }}

/* ══ CHAT ═══════════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {{
    background:transparent!important; border-radius:0!important; padding:3px 0!important;
    animation:fadeUp 0.18s ease forwards;
}}
.user-bubble {{
    background:{alpha(A,0.1) if not _LM else alpha(A,0.08)};
    border:1px solid {alpha(A,0.25)};
    border-radius:{"4px" if CLI else "14px 14px 4px 14px"};
    padding:10px 14px; margin:2px 0 2px 16%;
    font-size:13px; line-height:1.6; color:{TXT}; word-break:break-word;
}}
.assistant-bubble {{
    background:{SURFACE}; border:1px solid {BORDER};
    border-radius:{"4px" if CLI else "14px 14px 14px 4px"};
    padding:12px 16px; margin:2px 16% 2px 0;
    font-size:13px; line-height:1.75; color:{TXT}; word-break:break-word;
    transition:border-color 0.14s;
}}
.assistant-bubble:hover {{ border-color:{alpha(A,0.3)}!important; }}
[data-testid="stChatInput"] {{
    background:{SURFACE}!important; border:1px solid {alpha(A,0.28)}!important;
    border-radius:{INPUT_RADIUS}!important;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color:{A}!important; box-shadow:0 0 0 3px {alpha(A,0.11)}!important;
}}
[data-testid="stChatInputTextArea"] {{ color:{TXT}!important; background:transparent!important; }}
[data-testid="stChatInputTextArea"]::placeholder {{ color:{PLACEHOLDER}!important; }}

/* ══ MISC ════════════════════════════════════════════════════════ */
[data-testid="stAlert"] {{
    background:{alpha(A,0.07)}!important; border:1px solid {alpha(A,0.25)}!important;
    border-radius:{"4px" if CLI else "8px"}!important; color:{TXT}!important;
}}
[data-testid="stFileUploader"] {{
    background:{SURFACE}!important; border:1px dashed {alpha(A,0.25)}!important;
    border-radius:{"4px" if CLI else "10px"}!important;
}}
[data-testid="stFileUploader"]:hover {{ border-color:{A}!important; }}
::-webkit-scrollbar {{ width:3px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:{alpha(A,0.28)}; border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:{A}; }}
.stCaption {{ color:{TXT2}!important; font-size:11px!important; }}

@keyframes fadeUp {{ from{{opacity:0;transform:translateY(4px)}} to{{opacity:1;transform:translateY(0)}} }}
@keyframes fadeIn {{ from{{opacity:0}} to{{opacity:1}} }}
@keyframes shimmer {{ 0%{{background-position:-600px 0}} 100%{{background-position:600px 0}} }}

.shimmer-box {{
    border-radius:{"4px" if CLI else "10px"}; border:1px solid {BORDER};
    background:linear-gradient(90deg,{SURFACE} 0px,{SURFACE2} 160px,{SURFACE} 320px);
    background-size:600px 100%; animation:shimmer 1.4s ease-in-out infinite;
}}
.shimmer-line {{
    height:9px; border-radius:5px; margin-bottom:9px;
    background:linear-gradient(90deg,{SURFACE} 0px,{SURFACE2} 160px,{SURFACE} 320px);
    background-size:600px 100%; animation:shimmer 1.4s ease-in-out infinite;
}}
.shimmer-line.short{{width:55%;}} .shimmer-line.medium{{width:78%;}} .shimmer-line.long{{width:92%;}}
.token-bar-wrap{{ background:{BORDER}; border-radius:6px; height:3px; width:100%; margin-top:4px; overflow:hidden; }}
.token-bar-fill{{ height:3px; border-radius:6px; background:{A}; transition:width 0.4s ease; }}
.memory-badge{{
    display:inline-flex; align-items:center; gap:6px;
    background:{alpha(A,0.08)}; border:1px solid {alpha(A,0.25)};
    border-radius:{"2px" if CLI else "20px"}; color:{A};
    font-size:10px; padding:3px 11px; letter-spacing:0.05em; margin-bottom:10px;
}}
.cmd-result{{
    background:{SURFACE}; border:1px solid {BORDER};
    border-left:2px solid {A}; border-radius:{"4px" if CLI else "9px"};
    padding:12px 16px; margin:7px 0; font-size:13px; line-height:1.7; color:{TXT};
}}
.cmd-label{{ font-size:10px; color:{TXT2}; letter-spacing:0.08em; margin-bottom:6px; text-transform:uppercase; }}
.cli-prompt{{ color:{A}; font-size:11px; margin-bottom:2px; opacity:0.8; }}
.tmpl-card{{
    background:{SURFACE}; border:1px solid {BORDER};
    border-radius:{"4px" if CLI else "9px"}; padding:10px 12px; margin-bottom:6px;
    transition:border-color 0.14s;
}}
.tmpl-card:hover{{ border-color:{A}; }}
.tmpl-tag{{
    display:inline-block; background:{alpha(A,0.08)}; border:1px solid {alpha(A,0.2)};
    border-radius:{"2px" if CLI else "20px"}; color:{A};
    font-size:9px; padding:1px 6px; margin-right:3px; margin-bottom:3px;
}}
.swatch-row{{ display:flex; gap:7px; flex-wrap:wrap; margin:5px 0 10px; }}
.swatch{{
    width:20px; height:20px; border-radius:50%; cursor:pointer;
    border:2px solid transparent; transition:transform 0.13s; display:inline-block;
}}
.swatch.selected{{ transform:scale(1.3); box-shadow:0 0 0 2px {BG},0 0 0 4px currentColor; }}
.swatch:hover{{ transform:scale(1.15); }}
code,pre{{
    background:{SURFACE2}!important; border:1px solid {BORDER}!important;
    border-radius:{"2px" if CLI else "5px"}!important; color:{AL}!important;
}}
audio{{ filter:invert(0.85) hue-rotate(160deg) saturate(0.8)!important; width:100%!important; opacity:0.8; }}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTS ─────────────────────────────────────────────────────────────────
SARVAM_BASE = "https://api.sarvam.ai/v1"

PRESET_PROMPTS = {
    "🤖 Default":    "You are a helpful, concise AI assistant. Always format your responses using HTML tags only — never use markdown syntax like ** or ##. Use <b> for bold, <i> for italic, <br> for line breaks, <ul><li> for lists, <table border='1'> for tables, <code> for inline code, <pre><code> for code blocks. Do not wrap responses in ```html``` blocks, just output raw HTML directly.",
    "💻 Coder":      "You are an expert programmer. Always format responses in HTML. Use <pre><code> for all code blocks, <b> for key terms, <br> for spacing. Never use markdown.",
    "🎓 Tutor":      "You are a patient tutor. Format all responses in HTML using <b> for key concepts, <ul><li> for steps, <br> for spacing. Never use markdown.",
    "✍️ Writer":     "You are a creative writing assistant. Format responses in HTML using <b>, <i>, <br> tags. Never use markdown.",
    "🔬 Researcher": "You are a research assistant. Format responses in HTML using <b>, <ul><li>, <table> for structured data. Never use markdown.",
    "😂 Comedian":   "You are a witty AI. Format responses in HTML using <b> and <i> for emphasis. Never use markdown.",
}

ACCENT_PRESETS = [
    ("#db5151", "Red"),   ("#5191db", "Blue"),  ("#51db8a", "Green"),  ("#db9f51", "Amber"),
    ("#9b51db", "Purple"), ("#51d4db", "Cyan"),  ("#db5192", "Pink"),   ("#dbcb51", "Yellow"),
    ("#ffffff", "White"), ("#888888", "Grey"),
]

LANG_CODES = {
    "English":   "en-IN", "Hindi":     "hi-IN", "Tamil":    "ta-IN",
    "Telugu":    "te-IN", "Kannada":   "kn-IN", "Malayalam":"ml-IN",
}

SUGGESTIONS = [
    {"icon": "✍️", "title": "WRITE",      "prompt": "Write a short poem about the monsoon season in India"},
    {"icon": "🧠", "title": "EXPLAIN",    "prompt": "Explain quantum entanglement like I'm 15 years old"},
    {"icon": "🐛", "title": "DEBUG",      "prompt": "What's wrong with this Python code: `print('hello'`"},
    {"icon": "💡", "title": "BRAINSTORM", "prompt": "Give me 5 unique startup ideas for 2025 in the AI space"},
]

# ─── FEATURE 15: PROMPT TEMPLATES LIBRARY ──────────────────────────────────────
PROMPT_TEMPLATES = {
    "✉️ Email": [
        {"name": "Professional Email",    "tags": ["email","work"],
         "prompt": "Write a professional email to {recipient} about {topic}. Keep it concise and polite."},
        {"name": "Follow-up Email",       "tags": ["email","follow-up"],
         "prompt": "Write a follow-up email for a meeting/conversation about {topic}. Reference the previous discussion and suggest next steps."},
        {"name": "Apology Email",         "tags": ["email","apology"],
         "prompt": "Write a sincere apology email to {recipient} regarding {issue}. Acknowledge the problem and offer a solution."},
        {"name": "Cold Outreach Email",   "tags": ["email","sales"],
         "prompt": "Write a cold outreach email to {recipient} introducing myself and my product/service {product}. Make it compelling but not pushy."},
    ],
    "💻 Code": [
        {"name": "Code Review",           "tags": ["code","review"],
         "prompt": "Review the following code for bugs, performance issues, and best practices. Suggest improvements:\n\n```\n{code}\n```"},
        {"name": "Explain Code",          "tags": ["code","explain"],
         "prompt": "Explain what this code does step by step, as if explaining to a junior developer:\n\n```\n{code}\n```"},
        {"name": "Write Unit Tests",      "tags": ["code","testing"],
         "prompt": "Write comprehensive unit tests for the following function/class:\n\n```\n{code}\n```"},
        {"name": "Refactor Code",         "tags": ["code","refactor"],
         "prompt": "Refactor this code to be cleaner, more readable, and follow best practices:\n\n```\n{code}\n```"},
        {"name": "Debug This Error",      "tags": ["code","debug"],
         "prompt": "I'm getting this error: {error}\n\nHere is my code:\n\n```\n{code}\n```\n\nWhat is causing it and how do I fix it?"},
    ],
    "📝 Writing": [
        {"name": "Blog Post Outline",     "tags": ["writing","blog"],
         "prompt": "Create a detailed blog post outline for the topic: {topic}. Include an intro, 5 main sections with subpoints, and a conclusion."},
        {"name": "Summarise Article",     "tags": ["writing","summary"],
         "prompt": "Summarise the following article in 3-5 bullet points, highlighting the key takeaways:\n\n{article}"},
        {"name": "Improve Writing",       "tags": ["writing","edit"],
         "prompt": "Improve the clarity, flow, and grammar of this text while keeping the original meaning:\n\n{text}"},
        {"name": "LinkedIn Post",         "tags": ["writing","social"],
         "prompt": "Write an engaging LinkedIn post about {topic}. Make it professional, insightful, and end with a question to drive engagement."},
        {"name": "Product Description",   "tags": ["writing","marketing"],
         "prompt": "Write a compelling product description for {product}. Highlight key features, benefits, and include a call to action."},
    ],
    "🧠 Analysis": [
        {"name": "SWOT Analysis",         "tags": ["analysis","strategy"],
         "prompt": "Perform a SWOT analysis (Strengths, Weaknesses, Opportunities, Threats) for {subject}. Present it in a structured table format."},
        {"name": "Pros & Cons",           "tags": ["analysis","decision"],
         "prompt": "List the pros and cons of {topic} in a balanced, objective way. Include at least 5 points on each side."},
        {"name": "Compare Options",       "tags": ["analysis","compare"],
         "prompt": "Compare {option1} vs {option2} across these dimensions: features, cost, ease of use, scalability, and best use cases."},
        {"name": "Root Cause Analysis",   "tags": ["analysis","problem"],
         "prompt": "Perform a root cause analysis for this problem: {problem}. Use the 5 Whys technique and suggest solutions."},
    ],
    "🎓 Learning": [
        {"name": "Explain Like I'm 5",    "tags": ["learn","simple"],
         "prompt": "Explain {concept} in the simplest possible terms, as if explaining to a 5-year-old. Use analogies and examples."},
        {"name": "Study Plan",            "tags": ["learn","plan"],
         "prompt": "Create a 30-day study plan to learn {subject}. Break it into weekly goals with daily tasks and recommended resources."},
        {"name": "Quiz Me",               "tags": ["learn","quiz"],
         "prompt": "Create 10 multiple-choice quiz questions about {topic} with 4 options each. Mark the correct answer and provide a brief explanation."},
        {"name": "Flashcards",            "tags": ["learn","flashcard"],
         "prompt": "Create 10 flashcard-style Q&A pairs for studying {topic}. Format as Question: / Answer: pairs."},
    ],
    "🚀 Productivity": [
        {"name": "Meeting Agenda",        "tags": ["productivity","meeting"],
         "prompt": "Create a structured meeting agenda for a {duration} meeting about {topic}. Include time allocations for each item."},
        {"name": "Action Items",          "tags": ["productivity","tasks"],
         "prompt": "Extract all action items from this meeting notes/text and format them as a task list with owner and deadline fields:\n\n{notes}"},
        {"name": "Project Kickoff",       "tags": ["productivity","project"],
         "prompt": "Write a project kickoff document for {project_name}. Include: objective, scope, timeline, team roles, risks, and success metrics."},
        {"name": "Weekly Report",         "tags": ["productivity","report"],
         "prompt": "Write a concise weekly status report for {project}. Include: accomplishments this week, planned work next week, blockers, and metrics."},
    ],
}

# ─── API HELPERS ───────────────────────────────────────────────────────────────
def count_tokens_approx(text): return max(1, len(text.split()) * 4 // 3)

def call_sarvam_chat(api_key, model, messages_payload, max_tokens, temperature):
    r = requests.post(
        f"{SARVAM_BASE}/chat/completions",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={"model": model, "messages": messages_payload,
              "max_tokens": max_tokens, "temperature": temperature},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def strip_tags(text: str) -> str:
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def call_sarvam_tts(api_key, text, lang_code="en-IN"):
    r = requests.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={"text": strip_tags(text)[:2500], "target_language_code": lang_code,
              "speaker": "shubh", "model": "bulbul:v3"},
        timeout=30,
    )
    r.raise_for_status()
    audios = r.json().get("audios", [])
    return base64.b64decode(audios[0]) if audios else None

def autoplay_audio(audio_bytes: bytes):
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(f"""
    <audio autoplay style="display:none">
        <source src="data:audio/wav;base64,{b64}" type="audio/wav">
    </audio>
    """, unsafe_allow_html=True)

def call_sarvam_stt(api_key, audio_bytes, lang_code="en-IN"):
    r = requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={"api-subscription-key": api_key},
        files={"file": ("audio.wav", io.BytesIO(audio_bytes), "audio/wav")},
        data={"model": "saarika:v2", "language_code": lang_code},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("transcript", "")

def summarise_memory(api_key, messages):
    history = "\n".join([
        f"{m['role'].upper()}: {m['content'][:300]}"
        for m in messages[-20:]
        if m.get("content", "").strip()
    ])
    if not history.strip():
        return ""
    payload = [{"role": "user", "content": (
        "Summarise this conversation in under 120 words. "
        "Focus on key facts, topics discussed, and user preferences. Be terse.\n\n" + history
    )}]
    r = requests.post(
        f"{SARVAM_BASE}/chat/completions",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={"model": "sarvam-m", "messages": payload, "max_tokens": 200, "temperature": 0.3},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_sarvam_translate(api_key, text, source_lang, target_lang):
    r = requests.post(
        "https://api.sarvam.ai/translate",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={
            "input": text[:1000],
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "speaker_gender": "Male",
            "mode": "formal",
            "enable_preprocessing": True,
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("translated_text", "")

# ─── FEATURE 16: INLINE COMMAND PARSER ─────────────────────────────────────────
INLINE_COMMANDS = {
    "/translate": "Translate the last assistant reply to Hindi",
    "/summarise": "Summarise the entire conversation so far in 5 bullet points",
    "/speak":     "Read the last assistant reply aloud (TTS)",
    "/help":      "Show all available inline commands",
    "/clear":     "Clear the current chat session",
    "/stats":     "Show quick stats for this session",
}

def parse_inline_command(prompt: str):
    """Returns (command, args) if prompt starts with /, else (None, prompt)."""
    stripped = prompt.strip()
    if not stripped.startswith("/"):
        return None, stripped
    parts = stripped.split(None, 1)
    cmd   = parts[0].lower()
    args  = parts[1] if len(parts) > 1 else ""
    return cmd, args

def handle_inline_command(cmd, args, api_key, tts_lang):
    """Execute an inline command. Returns a dict with type and content."""
    if cmd == "/help":
        lines = "<b>Available inline commands:</b><br><br>"
        for c, desc in INLINE_COMMANDS.items():
            lines += f"<code>{c}</code> — {desc}<br>"
        return {"type": "info", "label": "HELP", "content": lines}

    if cmd == "/stats":
        msgs  = st.session_state.messages
        turns = len(msgs) // 2
        words = sum(len(m["content"].split()) for m in msgs)
        toks  = st.session_state.token_history[-1]["Tokens"] if st.session_state.token_history else 0
        return {"type": "info", "label": "SESSION STATS",
                "content": f"<b>Messages:</b> {len(msgs)}<br><b>Turns:</b> {turns}<br><b>Words:</b> {words}<br><b>Last tokens:</b> {toks}"}

    if cmd == "/clear":
        st.session_state.messages        = []
        st.session_state.token_history   = []
        st.session_state.memory_summary  = ""
        st.session_state.last_summarised = 0
        st.session_state.total_messages  = 0
        st.session_state.msg_translations= {}
        st.session_state.show_tr_picker  = {}
        save_current_session()
        return {"type": "info", "label": "CLEARED", "content": "Chat cleared."}

    if cmd == "/speak":
        if not api_key:
            return {"type": "error", "label": "ERROR", "content": "Add API key first."}
        assistant_msgs = [m for m in st.session_state.messages if m["role"] == "assistant"]
        if not assistant_msgs:
            return {"type": "error", "label": "ERROR", "content": "No assistant reply to speak."}
        last_reply = assistant_msgs[-1]["content"]
        try:
            ab = call_sarvam_tts(api_key, last_reply, LANG_CODES.get(tts_lang, "en-IN"))
            if ab:
                st.session_state.tts_audio = ab
            return {"type": "info", "label": "SPEAK", "content": "🔊 Playing last reply..."}
        except Exception as e:
            return {"type": "error", "label": "TTS ERROR", "content": str(e)}

    if cmd == "/translate":
        if not api_key:
            return {"type": "error", "label": "ERROR", "content": "Add API key first."}
        assistant_msgs = [m for m in st.session_state.messages if m["role"] == "assistant"]
        if not assistant_msgs:
            return {"type": "error", "label": "ERROR", "content": "No assistant reply to translate."}
        last_reply = strip_tags(assistant_msgs[-1]["content"])
        # Determine target language from args or default to Hindi
        target_name = args.strip().title() if args.strip() else "Hindi"
        if target_name not in LANG_CODES:
            target_name = "Hindi"
        try:
            translated = call_sarvam_translate(api_key, last_reply, "en-IN", LANG_CODES[target_name])
            return {"type": "translate", "label": f"TRANSLATED → {target_name.upper()}", "content": translated}
        except Exception as e:
            return {"type": "error", "label": "TRANSLATE ERROR", "content": str(e)}

    if cmd == "/summarise":
        if not api_key:
            return {"type": "error", "label": "ERROR", "content": "Add API key first."}
        if not st.session_state.messages:
            return {"type": "error", "label": "ERROR", "content": "No messages to summarise."}
        try:
            history = "\n".join([
                f"{m['role'].upper()}: {strip_tags(m['content'])[:300]}"
                for m in st.session_state.messages[-20:]
            ])
            payload = [{"role": "user", "content":
                "Summarise this conversation in exactly 5 bullet points. Be concise.\n\n" + history}]
            r = requests.post(
                f"{SARVAM_BASE}/chat/completions",
                headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
                json={"model": "sarvam-m", "messages": payload, "max_tokens": 300, "temperature": 0.3},
                timeout=20,
            )
            r.raise_for_status()
            summary = r.json()["choices"][0]["message"]["content"]
            return {"type": "info", "label": "CONVERSATION SUMMARY", "content": summary}
        except Exception as e:
            return {"type": "error", "label": "SUMMARISE ERROR", "content": str(e)}

    return {"type": "error", "label": "UNKNOWN COMMAND",
            "content": f"Unknown command <code>{cmd}</code>. Type <code>/help</code> for a list."}

# ─── NAV TABS ──────────────────────────────────────────────────────────────────
# TABS is now just used for reference; sidebar is built manually below
TABS = []  # kept for compatibility

# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
_col = st.session_state.nav_collapsed

# Secondary tabs shown inside the wrench expander
SECONDARY_TABS = [
    ("memory",    "🧠", "Memory"),
    ("translate", "🌐", "Translate"),
    ("search",    "🔍", "Search"),
    ("voice",     "🎙", "Voice"),
    ("upload",    "📎", "Upload"),
    ("stats",     "📈", "Stats"),
    ("favs",      "★",  "Favourites"),
    ("templates", "📝", "Templates"),
]

with st.sidebar:
    # ── Logo (expanded only) ──────────────────────────────────────────────────
    if not _col:
        st.markdown(f"""
        <div style='padding:10px 16px 8px;border-bottom:1px solid {SB_BDR};margin-bottom:2px;'>
            <div style='font-size:10px;font-weight:600;letter-spacing:0.13em;color:{A};'>◈ SARVAM</div>
            <div style='font-size:8px;color:{TXT2};margin-top:1px;'>powered by sarvam ai</div>
        </div>""", unsafe_allow_html=True)

    # ── Chat button (always visible, primary action) ──────────────────────────
    _chat_active = st.session_state.active_tab == "chat"
    st.markdown(f"<div class='{'nav-active' if _chat_active else 'nav-item'}'>", unsafe_allow_html=True)
    if st.button("💬" if _col else "💬  Chat", key="nav_chat", use_container_width=True, help="Chat"):
        st.session_state.active_tab = "chat"; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Wrench expander — other tabs (expanded sidebar only) ──────────────────
    if not _col:
        with st.expander("🔧  Tools", expanded=(st.session_state.active_tab in [t[0] for t in SECONDARY_TABS])):
            for _tid, _icon, _label in SECONDARY_TABS:
                _active = st.session_state.active_tab == _tid
                st.markdown(f"<div class='{'nav-active' if _active else 'nav-item'}'>", unsafe_allow_html=True)
                if st.button(f"{_icon}  {_label}", key=f"nav_{_tid}", use_container_width=True):
                    st.session_state.active_tab = _tid; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # ── Session history (expanded only) ──────────────────────────────────────
    if not _col:
        st.divider()
        # Current session name + new session
        _cur_name = st.session_state.sessions.get(st.session_state.active_session, {}).get("name", "")
        st.markdown(f"<div style='font-size:9px;color:{TXT2};letter-spacing:0.08em;text-transform:uppercase;padding:2px 0 4px;'>{_cur_name}</div>", unsafe_allow_html=True)

        _n1, _n2 = st.columns([3, 1])
        with _n1:
            _nn = st.text_input("", placeholder="new session…", key="new_sess_name", label_visibility="collapsed")
        with _n2:
            if st.button("＋", key="add_session"):
                save_current_session()
                _sid = new_session(_nn.strip() or None)
                switch_session(_sid); st.rerun()

        # Chat history — message previews for current session
        if st.session_state.messages:
            st.markdown(f"<div style='font-size:9px;color:{TXT2};letter-spacing:0.07em;text-transform:uppercase;padding:4px 0 3px;'>History</div>", unsafe_allow_html=True)
            for _hi, _hm in enumerate(reversed(st.session_state.messages[-8:])):
                _role_short = "you" if _hm["role"] == "user" else "ai"
                _preview = strip_tags(_hm["content"])[:40].replace("\n", " ")
                _clr = A if _hm["role"] == "user" else TXT2
                st.markdown(f"<div style='font-size:10px;color:{_clr};padding:1px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'><span style='opacity:0.5;font-size:9px;'>{_role_short}</span> {_preview}</div>", unsafe_allow_html=True)

        # Sessions list
        st.markdown(f"<div style='font-size:9px;color:{TXT2};letter-spacing:0.07em;text-transform:uppercase;padding:6px 0 3px;'>Sessions</div>", unsafe_allow_html=True)
        for _sid, _sess in list(st.session_state.sessions.items()):
            _ia = _sid == st.session_state.active_session
            _c1, _c2 = st.columns([5, 1])
            with _c1:
                if st.button(f"{'▶ ' if _ia else ''}{_sess['name']} ({len(_sess['messages'])})",
                             key=f"sess_{_sid}", use_container_width=True):
                    if not _ia:
                        save_current_session(); switch_session(_sid); st.rerun()
            with _c2:
                if len(st.session_state.sessions) > 1:
                    if st.button("✕", key=f"del_{_sid}"):
                        if _ia:
                            _o = [k for k in st.session_state.sessions if k != _sid]
                            if _o: switch_session(_o[0])
                        del st.session_state.sessions[_sid]; st.rerun()

        if st.button("＋ New chat", use_container_width=True, key="new_chat_btn"):
            st.session_state.messages = []; st.session_state.token_history = []
            st.session_state.tts_audio = None; st.session_state.memory_summary = ""
            st.session_state.last_summarised = 0; st.session_state.total_messages = 0
            save_current_session(); st.rerun()
        if st.session_state.messages:
            _exp_data = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages)
            st.download_button("↓ export chat", data=_exp_data, file_name="chat.txt", mime="text/plain", use_container_width=True)

    # ── Settings + Collapse — fixed to bottom of sidebar ────────────────────
    st.markdown("<div class='sb-bottom'>", unsafe_allow_html=True)

    _settings_active = st.session_state.active_tab == "settings"
    st.markdown(f"<div class='{'nav-active' if _settings_active else 'nav-item'}'>", unsafe_allow_html=True)
    if st.button("⚙" if _col else "⚙  Settings", key="nav_settings", use_container_width=True, help="Settings"):
        st.session_state.active_tab = "settings"; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='nav-collapse'>", unsafe_allow_html=True)
    if st.button("›" if _col else "‹", key="nav_toggle", use_container_width=True,
                 help="Expand" if _col else "Collapse"):
        st.session_state.nav_collapsed = not _col; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    # padding so scrollable content doesn't hide behind fixed bottom
    st.markdown("<div style='height:90px'></div>", unsafe_allow_html=True)

# ─── PULL SETTINGS FROM SESSION STATE ─────────────────────────────────────────
api_key      = st.session_state.get("api_key", "")
model        = "sarvam-m"
DEFAULT_PROMPT = PRESET_PROMPTS["🤖 Default"]
system_prompt  = st.session_state.get("sys_prompt_input") or DEFAULT_PROMPT
temperature    = st.session_state.get("temp_s",   0.7)
max_tokens     = st.session_state.get("tok_s",    1024)
stream_mode    = st.session_state.get("stream_t", True)
tts_enabled    = st.session_state.get("tts_t",    True)
tts_lang       = st.session_state.get("tts_l",    "Hindi")
stt_lang       = st.session_state.get("stt_l",    "English")
mem_auto       = st.session_state.get("mem_auto", True)

TAB = st.session_state.active_tab


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "chat":

    # Active session badge
    cur_sess_name = st.session_state.sessions.get(st.session_state.active_session, {}).get("name", "")
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px;'>
        <div style='font-size:10px;color:#444;letter-spacing:0.06em;'>SESSION:</div>
        <div style='font-size:10px;color:{A};letter-spacing:0.06em;font-weight:600;'>{cur_sess_name}</div>
    </div>
    """, unsafe_allow_html=True)

    # Memory badge
    if st.session_state.memory_summary:
        st.markdown(f"<div class='memory-badge'>🧠 MEMORY ACTIVE — {len(st.session_state.memory_summary.split())} words compressed</div>", unsafe_allow_html=True)

    # ── INLINE COMMAND HINT ─────────────────────────────────────────────────
    st.markdown(f"""
    <div style='font-size:10px;color:#2a2a2a;margin-bottom:12px;letter-spacing:0.04em;'>
        💡 type <code style='color:#3a3a3a;'>/help</code> for inline commands &nbsp;·&nbsp;
        <code style='color:#3a3a3a;'>/translate</code> &nbsp;
        <code style='color:#3a3a3a;'>/summarise</code> &nbsp;
        <code style='color:#3a3a3a;'>/speak</code> &nbsp;
        <code style='color:#3a3a3a;'>/clear</code> &nbsp;
        <code style='color:#3a3a3a;'>/stats</code>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.messages:
        prefix = "root@sarvam:~$ " if CLI else ""
        st.markdown(f"""
        <div style='padding:40px 0 24px 0;animation:fadeIn 0.4s ease;'>
            <div style='font-size:{"1.2rem" if CLI else "1.6rem"};font-weight:300;color:#e8e8e8;letter-spacing:{"-0.02em" if not CLI else "0.04em"};'>
                {prefix}{"what do you need?" if not CLI else "SARVAM_AGENT v1.0 — READY"}
            </div>
            <div style='color:#2a2a2a;font-size:11px;margin-top:6px;letter-spacing:0.04em;'>
                {"open ⚙️ Settings in the nav → paste api key → start chatting" if not CLI else "[add api key] → [type command below]"}
            </div>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(4)
        for i, s in enumerate(SUGGESTIONS):
            with cols[i]:
                lbl = f"[{s['title']}]" if CLI else f"{s['icon']} {s['title']}"
                if st.button(lbl, use_container_width=True, key=f"sug_{i}"):
                    st.session_state.messages.append({"role": "user", "content": s["prompt"]})
                    st.rerun()
    else:
        for idx, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    if CLI:
                        st.markdown(f"<div class='cli-prompt'>user@sarvam:~$</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='user-bubble'>{msg['content']}</div>", unsafe_allow_html=True)
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    if CLI:
                        st.markdown(f"<div class='cli-prompt'>&gt;&gt; sarvam-m output:</div>", unsafe_allow_html=True)

                    st.markdown(f"<div class='assistant-bubble'>{msg['content'].replace(chr(92)+'n', chr(10))}</div>", unsafe_allow_html=True)

                    eb1, eb2, eb3, _ = st.columns([1, 1, 1, 7])
                    with eb1:
                        if st.button("⭐", key=f"fav_{idx}", help="Save to favourites"):
                            if msg["content"] not in st.session_state.favourites:
                                st.session_state.favourites.append(msg["content"])
                                st.toast("Saved!", icon="⭐")
                    with eb2:
                        if api_key and st.button("🔊", key=f"tts_{idx}", help="Read aloud"):
                            with st.spinner(""):
                                try:
                                    ab = call_sarvam_tts(api_key, msg["content"], LANG_CODES.get(tts_lang, "en-IN"))
                                    if ab: st.session_state.tts_audio = ab; st.rerun()
                                except Exception as e:
                                    st.error(f"TTS: {e}")
                    with eb3:
                        tr_open = st.session_state.show_tr_picker.get(idx, False)
                        if st.button("🌐", key=f"tr_open_{idx}", help="Translate"):
                            st.session_state.show_tr_picker[idx] = not tr_open
                            st.rerun()

                    if st.session_state.show_tr_picker.get(idx, False):
                        pk1, pk2, pk3 = st.columns([2, 1, 1])
                        with pk1:
                            pick_lang = st.selectbox(
                                "translate to",
                                [l for l in LANG_CODES.keys() if l != "English"],
                                key=f"tr_pick_{idx}",
                                label_visibility="collapsed",
                            )
                        with pk2:
                            if st.button("GO", key=f"tr_go_{idx}", use_container_width=True):
                                if not api_key:
                                    st.warning("add api key first")
                                else:
                                    with st.spinner(f"translating to {pick_lang}..."):
                                        try:
                                            translated = call_sarvam_translate(
                                                api_key, strip_tags(msg["content"]),
                                                "en-IN", LANG_CODES[pick_lang],
                                            )
                                            st.session_state.msg_translations[idx] = {"lang": pick_lang, "text": translated}
                                            st.session_state.show_tr_picker[idx] = False
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"translate error: {e}")
                        with pk3:
                            if st.button("✕", key=f"tr_close_{idx}", use_container_width=True):
                                st.session_state.show_tr_picker[idx] = False
                                st.rerun()

                    if idx in st.session_state.msg_translations:
                        tr = st.session_state.msg_translations[idx]
                        st.markdown(f"""
                        <div style='background:#0f0f0f;border:1px solid #1e1e1e;
                                    border-left:3px solid {A};border-radius:12px;
                                    padding:14px 16px;margin-top:8px;'>
                            <div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:8px;'>
                                🌐 {tr["lang"].upper()}
                            </div>
                            <div style='font-size:14px;color:#e8e8e8;line-height:1.7;'>{tr["text"]}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        tb1, tb2, tb3, _ = st.columns([1, 1, 1, 7])
                        with tb1:
                            if st.button("⭐", key=f"fav_tr_{idx}", help="Save translation"):
                                if tr["text"] not in st.session_state.favourites:
                                    st.session_state.favourites.append(tr["text"])
                                    st.toast("Saved!", icon="⭐")
                        with tb2:
                            if api_key and st.button("🔊", key=f"tts_tr_{idx}", help="Read translation"):
                                with st.spinner(""):
                                    try:
                                        ab = call_sarvam_tts(api_key, tr["text"], LANG_CODES[tr["lang"]])
                                        if ab: st.session_state.tts_audio = ab; st.rerun()
                                    except Exception as e:
                                        st.error(f"TTS: {e}")
                        with tb3:
                            if st.button("🌐", key=f"tr_again_{idx}", help="Translate again"):
                                st.session_state.show_tr_picker[idx] = True
                                del st.session_state.msg_translations[idx]
                                st.rerun()

    # ── INLINE COMMAND RESULT DISPLAY ──────────────────────────────────────
    if st.session_state.cmd_result:
        res = st.session_state.cmd_result
        border_col = A if res["type"] != "error" else "#db5151"
        st.markdown(f"""
        <div class='cmd-result' style='border-left-color:{border_col};'>
            <div class='cmd-label'>{res["label"]}</div>
            <div>{res["content"]}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✕ dismiss", key="dismiss_cmd"):
            st.session_state.cmd_result = None
            st.rerun()

    if st.session_state.tts_audio:
        autoplay_audio(st.session_state.tts_audio)
        st.session_state.tts_audio = None

    counter_slot = st.empty()

    if prompt := st.chat_input("message... or /help for commands" if not CLI else "root@sarvam:~$ ", key="chat_input"):
        if not api_key:
            st.warning("⚠️ paste your api key in the sidebar first")
            st.stop()

        # ── FEATURE 16: Check for inline command ───────────────────────────
        cmd, args = parse_inline_command(prompt)
        if cmd and cmd in INLINE_COMMANDS:
            with st.spinner(f"running {cmd}..."):
                result = handle_inline_command(cmd, args, api_key, tts_lang)
            st.session_state.cmd_result = result
            save_current_session()
            st.rerun()
        else:
            # Normal chat flow
            tok = count_tokens_approx(prompt)
            pct = min(tok / max_tokens * 100, 100)
            bar_col = AL if pct < 60 else A if pct < 90 else AD
            counter_slot.markdown(f"""
            <div style='font-size:10px;color:#333;margin-bottom:4px;letter-spacing:0.04em;'>~{tok} tokens</div>
            <div class='token-bar-wrap'><div class='token-bar-fill' style='width:{pct}%;background:{bar_col};'></div></div>
            """, unsafe_allow_html=True)

            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.total_messages += 1
            st.session_state.cmd_result = None

            with st.chat_message("user", avatar="👤"):
                if CLI: st.markdown(f"<div class='cli-prompt'>user@sarvam:~$</div>", unsafe_allow_html=True)
                st.markdown(prompt)

            if st.session_state.memory_summary:
                sys_content = f"{system_prompt}\n\nContext from earlier in this conversation:\n{st.session_state.memory_summary}"
            else:
                sys_content = system_prompt

            first_msg = f"{sys_content}\n\n---\n\nLet's begin."
            messages_payload = [
                {"role": "user",      "content": first_msg},
                {"role": "assistant", "content": "Understood. I'm ready to help."},
                *[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                    if m.get("content", "").strip()
                ],
            ]

            with st.chat_message("assistant", avatar="🤖"):
                if CLI: st.markdown(f"<div class='cli-prompt'>&gt;&gt; sarvam-m output:</div>", unsafe_allow_html=True)
                placeholder = st.empty()
                # ── Shimmer skeleton while waiting for API ──
                placeholder.markdown(f"""
                <div class='shimmer-box' style='padding:18px 20px;margin:4px 20% 4px 0;'>
                    <div class='shimmer-line long'></div>
                    <div class='shimmer-line medium'></div>
                    <div class='shimmer-line short'></div>
                </div>
                """, unsafe_allow_html=True)
                try:
                    data  = call_sarvam_chat(api_key, model, messages_payload, max_tokens, temperature)
                    reply = data["choices"][0]["message"]["content"]

                    usage     = data.get("usage", {})
                    total_tok = usage.get("total_tokens", count_tokens_approx(reply))
                    st.session_state.token_history.append({
                        "Turn": len(st.session_state.messages) // 2 + 1,
                        "Tokens": total_tok
                    })

                    if stream_mode:
                        displayed = ""
                        for i, char in enumerate(reply):
                            displayed += char
                            if i % 4 == 0:
                                placeholder.markdown(
                                    f"<div class='assistant-bubble'>{displayed}{'█' if CLI else '▌'}</div>",
                                    unsafe_allow_html=True
                                )
                                time.sleep(0.007)
                        placeholder.markdown(
                            f"<div class='assistant-bubble'>{reply.replace(chr(92)+'n', chr(10))}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        placeholder.markdown(
                            f"<div class='assistant-bubble'>{reply.replace(chr(92)+'n', chr(10))}</div>",
                            unsafe_allow_html=True
                        )

                    if tts_enabled and api_key:
                        try:
                            ab = call_sarvam_tts(api_key, reply, LANG_CODES.get(tts_lang, "en-IN"))
                            if ab: st.session_state.tts_audio = ab
                        except: pass

                    turns = len(st.session_state.messages) // 2
                    if mem_auto and api_key and turns > 0 and turns % 10 == 0 and turns != st.session_state.last_summarised:
                        with st.spinner("🧠 compressing memory..."):
                            try:
                                st.session_state.memory_summary  = summarise_memory(api_key, st.session_state.messages)
                                st.session_state.last_summarised = turns
                            except: pass

                except requests.exceptions.HTTPError as e:
                    reply = f"❌ {e.response.status_code}: {str(e)}"
                    placeholder.error(reply)
                except requests.exceptions.Timeout:
                    reply = "⏱️ timed out — try again"
                    placeholder.error(reply)
                except Exception as e:
                    reply = f"❌ {str(e)}"
                    placeholder.error(reply)

            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.total_messages += 1
            save_current_session()
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MEMORY
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "memory":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// MEMORY' if CLI else '🧠  CONVERSATION MEMORY'}</div>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.memory_summary:
        st.markdown(f"<div class='memory-badge'>ACTIVE — last compressed at turn {st.session_state.last_summarised}</div>", unsafe_allow_html=True)
        st.markdown("""<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>COMPRESSED SUMMARY</div>""", unsafe_allow_html=True)
        edited_mem = st.text_area("", value=st.session_state.memory_summary, height=160, key="mem_edit")
        mc1, mc2 = st.columns(2)
        with mc1:
            if st.button("SAVE EDITS", use_container_width=True):
                st.session_state.memory_summary = edited_mem
                st.toast("Memory updated!", icon="🧠")
        with mc2:
            if st.button("CLEAR MEMORY", use_container_width=True):
                st.session_state.memory_summary  = ""
                st.session_state.last_summarised = 0
                st.rerun()
    else:
        st.markdown("""<div style='color:#222;font-size:12px;padding:20px 0;'>no memory yet</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("""<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:10px;'>MANUAL SUMMARISE</div>""", unsafe_allow_html=True)
    if st.button("🧠 SUMMARISE NOW", use_container_width=False):
        if not api_key:
            st.warning("add api key first")
        elif not st.session_state.messages:
            st.warning("no messages to summarise")
        else:
            with st.spinner("compressing..."):
                try:
                    st.session_state.memory_summary  = summarise_memory(api_key, st.session_state.messages)
                    st.session_state.last_summarised = len(st.session_state.messages) // 2
                    st.success("memory updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"error: {e}")

    st.markdown("""<div style='font-size:10px;color:#222;margin-top:12px;line-height:1.8;'>
        memory is injected into every system prompt so the model remembers earlier turns<br>
        auto-summarise triggers every 10 turns if enabled in settings
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRANSLATE
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "translate":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// TRANSLATE' if CLI else '🌐  TRANSLATE MESSAGE'}</div>", unsafe_allow_html=True)
    st.divider()

    tr_col1, tr_col2 = st.columns(2)
    with tr_col1:
        tr_source = st.selectbox("FROM", list(LANG_CODES.keys()), index=0, key="tr_src")
    with tr_col2:
        tr_target = st.selectbox("TO",   list(LANG_CODES.keys()), index=1, key="tr_tgt")

    tr_text = st.text_area("TEXT TO TRANSLATE", height=120, placeholder="type or paste text here...", key="tr_input")

    if st.button("🌐 TRANSLATE", use_container_width=True, key="do_translate"):
        if not api_key:
            st.warning("⚠️ add api key in sidebar")
        elif not tr_text.strip():
            st.warning("enter some text first")
        else:
            with st.spinner("translating..."):
                try:
                    result = call_sarvam_translate(api_key, tr_text, LANG_CODES[tr_source], LANG_CODES[tr_target])
                    st.session_state.translate_results["last"] = {
                        "original": tr_text, "translated": result,
                        "from": tr_source, "to": tr_target,
                    }
                except Exception as e:
                    st.error(f"translate error: {e}")

    if st.session_state.translate_results.get("last"):
        res = st.session_state.translate_results["last"]
        st.divider()
        st.markdown(f"<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>{res['from'].upper()} → {res['to'].upper()}</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='background:#0f0f0f;border:1px solid #1e1e1e;border-radius:12px;padding:16px;font-size:14px;line-height:1.7;color:#e8e8e8;'>
            {res['translated']}
        </div>
        """, unsafe_allow_html=True)
        tr_c1, tr_c2 = st.columns(2)
        with tr_c1:
            if st.button("SEND TO CHAT →", use_container_width=True, key="tr_send"):
                st.session_state.messages.append({"role": "user", "content": res["translated"]})
                st.session_state.total_messages += 1
                st.success("sent! switch to 💬 CHAT")
        with tr_c2:
            if api_key and st.button("🔊 SPEAK", use_container_width=True, key="tr_tts"):
                with st.spinner("generating audio..."):
                    try:
                        ab = call_sarvam_tts(api_key, res["translated"], LANG_CODES[res["to"]])
                        if ab:
                            st.session_state.tts_audio = ab
                            st.rerun()
                    except Exception as e:
                        st.error(f"TTS: {e}")

    st.divider()
    st.markdown("<div style='font-size:10px;color:#222;line-height:1.8;'>translate any message from chat → use it in conversation or hear it spoken</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SEARCH
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "search":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// SEARCH CHAT' if CLI else '🔍  SEARCH CHAT HISTORY'}</div>", unsafe_allow_html=True)
    st.divider()

    search_q = st.text_input("SEARCH TERM", placeholder="search messages...", key="search_input")

    if search_q.strip():
        hits = [
            (i, m) for i, m in enumerate(st.session_state.messages)
            if search_q.lower() in m["content"].lower()
        ]
        st.markdown(f"<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:12px;'>{len(hits)} result(s) for '{search_q}'</div>", unsafe_allow_html=True)

        if not hits:
            st.markdown("<div style='color:#222;font-size:12px;padding:20px 0;'>nothing found</div>", unsafe_allow_html=True)
        else:
            for idx, msg in hits:
                role_label = "YOU" if msg["role"] == "user" else "ASSISTANT"
                raw = strip_tags(msg["content"])
                highlighted = re.sub(
                    f"({re.escape(search_q)})",
                    f"<mark style='background:{A};color:#000;padding:0 2px;border-radius:3px;'>\\1</mark>",
                    raw, flags=re.IGNORECASE
                )
                st.markdown(f"""
                <div style='background:#0f0f0f;border:1px solid #1e1e1e;border-radius:12px;
                            padding:12px 16px;margin-bottom:10px;'>
                    <div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>
                        MSG #{idx+1} · {role_label}
                    </div>
                    <div style='font-size:13px;color:#e8e8e8;line-height:1.6;'>
                        {highlighted[:400]}{"..." if len(raw) > 400 else ""}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        total = len(st.session_state.messages)
        st.markdown(f"<div style='color:#222;font-size:12px;padding:10px 0;'>{total} messages in history — type to search</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — VOICE
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "voice":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// VOICE INPUT' if CLI else '🎤  VOICE INPUT'}</div>", unsafe_allow_html=True)
    st.divider()

    voice_lang     = st.selectbox("TRANSCRIPTION LANGUAGE", list(LANG_CODES.keys()), key="voice_lang_tab")
    uploaded_audio = st.file_uploader("UPLOAD AUDIO (.wav .mp3 .ogg)", type=["wav","mp3","ogg"], key="voice_upload")

    if uploaded_audio:
        st.audio(uploaded_audio)
        if st.button("🎤 TRANSCRIBE", use_container_width=True):
            if not api_key: st.warning("⚠️ add api key in sidebar")
            else:
                with st.spinner("transcribing..."):
                    try:
                        st.session_state.stt_result = call_sarvam_stt(
                            api_key, uploaded_audio.read(), LANG_CODES.get(voice_lang, "en-IN")
                        )
                    except Exception as e:
                        st.error(f"STT error: {e}")

    if st.session_state.stt_result:
        st.markdown("""<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-top:16px;'>TRANSCRIPT</div>""", unsafe_allow_html=True)
        edited = st.text_area("", value=st.session_state.stt_result, height=100, key="stt_edit")
        if st.button("SEND TO CHAT →", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": edited})
            st.session_state.total_messages += 1
            st.session_state.stt_result = ""
            st.success("sent! switch to 💬 CHAT tab")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "upload":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// FILE UPLOAD' if CLI else '📁  FILE & IMAGE UPLOAD'}</div>", unsafe_allow_html=True)
    st.divider()

    uploaded_file = st.file_uploader("UPLOAD FILE OR IMAGE",
        type=["txt","py","js","json","csv","md","png","jpg","jpeg","pdf"], key="file_upload")

    if uploaded_file:
        if uploaded_file.type.startswith("image/"):
            st.image(uploaded_file, caption=uploaded_file.name, width=400)
            context = f"[Image attached: {uploaded_file.name}]"
        else:
            try:
                content = uploaded_file.read().decode("utf-8", errors="replace")
                st.markdown(f"<div style='font-size:10px;color:#444;margin-bottom:6px;'>PREVIEW — {uploaded_file.name}</div>", unsafe_allow_html=True)
                st.code(content[:2000] + ("..." if len(content) > 2000 else ""), language="text")
                context = f"File: {uploaded_file.name}\n\n```\n{content[:3000]}\n```"
            except:
                context = f"[Binary file: {uploaded_file.name}]"

        user_note = st.text_input("QUESTION ABOUT THIS FILE", placeholder="summarise / what does this code do?")
        if st.button("ATTACH & SEND →", use_container_width=True):
            if not api_key: st.warning("⚠️ add api key first")
            else:
                full = f"{user_note}\n\n{context}" if user_note else context
                st.session_state.messages.append({"role": "user", "content": full})
                st.session_state.total_messages += 1
                st.success("attached! switch to 💬 CHAT")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — STATS
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "stats":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// STATS' if CLI else '📊  SESSION STATS'}</div>", unsafe_allow_html=True)
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("MESSAGES", st.session_state.total_messages)
    with c2: st.metric("TURNS",    len(st.session_state.messages) // 2)
    with c3:
        tw = sum(len(m["content"].split()) for m in st.session_state.messages)
        st.metric("WORDS", tw)

    st.divider()

    if st.session_state.token_history:
        st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>TOKENS PER TURN</div>", unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.token_history)
        st.bar_chart(df.set_index("Turn"), color=A, height=240)

        if st.session_state.messages:
            st.divider()
            st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>WORDS PER MESSAGE</div>", unsafe_allow_html=True)
            lengths = pd.DataFrame([
                {"#": i+1, "Role": m["role"].upper(), "Words": len(m["content"].split())}
                for i, m in enumerate(st.session_state.messages)
            ])
            ca, cb = st.columns(2)
            with ca:
                st.caption("YOU")
                u = lengths[lengths["Role"]=="USER"][["#","Words"]].set_index("#")
                st.bar_chart(u, color=AL, height=160)
            with cb:
                st.caption("ASSISTANT")
                a = lengths[lengths["Role"]=="ASSISTANT"][["#","Words"]].set_index("#")
                st.bar_chart(a, color=AD, height=160)
    else:
        st.markdown("<div style='color:#1e1e1e;font-size:12px;padding:30px 0;'>no data yet</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — FAVOURITES
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "favs":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// FAVOURITES' if CLI else '⭐  SAVED RESPONSES'}</div>", unsafe_allow_html=True)
    st.divider()

    if not st.session_state.favourites:
        st.markdown("<div style='color:#1e1e1e;font-size:12px;padding:20px 0;'>nothing saved — hit ⭐ on any reply</div>", unsafe_allow_html=True)
    else:
        for i, fav in enumerate(st.session_state.favourites):
            with st.expander(f"{'[FAV_' + str(i+1) + ']' if CLI else '⭐ response #' + str(i+1)} — {len(fav.split())} words"):
                st.markdown(fav)
                if st.button("REMOVE", key=f"del_fav_{i}"):
                    st.session_state.favourites.pop(i); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 10 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "settings":
    st.markdown("### ⚙️  Settings")
    st.divider()

    # API KEY
    st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;'>API Key</div>", unsafe_allow_html=True)
    _nk = st.text_input("Sarvam API Key", type="password",
                         value=st.session_state.api_key,
                         placeholder="paste your sarvam.ai key here…",
                         key="api_key_input")
    _k1, _k2, _ = st.columns([1, 1, 4])
    with _k1:
        if st.button("Save", key="save_api"):
            st.session_state.api_key = _nk
            st.toast("API key saved!", icon="🔑")
    with _k2:
        if st.session_state.api_key and st.button("Clear", key="clear_api"):
            st.session_state.api_key = ""; st.rerun()
    if st.session_state.api_key:
        st.caption(f"● key set · {len(st.session_state.api_key)} chars")

    st.divider()
    _cl, _cr = st.columns([1.2, 1])

    with _cl:
        st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;'>System Prompt</div>", unsafe_allow_html=True)
        _pc = st.selectbox("Preset", list(PRESET_PROMPTS.keys()), label_visibility="collapsed", key="preset_sel")
        st.text_area("System Prompt", value=PRESET_PROMPTS[_pc], height=80, key="sys_prompt_input")
        st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.08em;text-transform:uppercase;margin:10px 0 6px;'>Generation</div>", unsafe_allow_html=True)
        _g1, _g2 = st.columns(2)
        with _g1: st.slider("Temp", 0.0, 1.0, 0.7, 0.05, key="temp_s")
        with _g2: st.select_slider("Tokens", [256,512,1024,2048], value=1024, key="tok_s")
        _g3, _g4 = st.columns(2)
        with _g3: st.toggle("Streaming", value=True, key="stream_t")
        with _g4: st.toggle("Auto TTS",  value=True, key="tts_t")
        st.selectbox("TTS lang", list(LANG_CODES.keys()), index=list(LANG_CODES.keys()).index("Hindi"), key="tts_l")
        st.selectbox("Mic lang", list(LANG_CODES.keys()), key="stt_l")
        st.toggle("Auto-summarise memory every 10 turns", value=True, key="mem_auto")

    with _cr:
        st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;'>Accent Colour</div>", unsafe_allow_html=True)

        # Native colour picker widget — picks and applies immediately
        _picked = st.color_picker("Pick accent", value=st.session_state.accent, key="color_picker_widget")
        if _picked != st.session_state.accent:
            st.session_state.accent = _picked; st.rerun()

        st.caption(f"current: {st.session_state.accent}")

        st.divider()
        st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;'>Interface</div>", unsafe_allow_html=True)
        _lm = st.toggle("Light mode", value=st.session_state.get("light_mode", False), key="light_mode_toggle")
        if _lm != st.session_state.get("light_mode", False):
            st.session_state.light_mode = _lm; st.rerun()
        _cli = st.toggle("CLI mode", value=st.session_state.cli_mode, key="cli_toggle")
        if _cli != st.session_state.cli_mode:
            st.session_state.cli_mode = _cli; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — TEMPLATES  (Feature 15)
# ══════════════════════════════════════════════════════════════════════════════
if TAB == "templates":
    st.markdown(f"<div style='padding:20px 0 10px 0;font-size:1rem;font-weight:500;color:#e8e8e8;letter-spacing:0.06em;'>{'// PROMPT TEMPLATES' if CLI else '📋  PROMPT TEMPLATES LIBRARY'}</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:11px;color:#333;margin-bottom:16px;letter-spacing:0.04em;'>click any template to load it into the editor below, fill in the placeholders, then send to chat</div>", unsafe_allow_html=True)
    st.divider()

    # ── Category filter ──────────────────────────────────────────────────────
    all_categories = list(PROMPT_TEMPLATES.keys())
    tmpl_search    = st.text_input("🔍 SEARCH TEMPLATES", placeholder="email, code, blog...", key="tmpl_search")

    # Filter categories/templates by search
    def templates_match(search):
        results = {}
        for cat, items in PROMPT_TEMPLATES.items():
            matched = [t for t in items if
                       search.lower() in t["name"].lower() or
                       search.lower() in t["prompt"].lower() or
                       any(search.lower() in tag for tag in t["tags"])]
            if matched:
                results[cat] = matched
        return results

    display_templates = templates_match(tmpl_search) if tmpl_search.strip() else PROMPT_TEMPLATES

    if not display_templates:
        st.markdown("<div style='color:#222;font-size:12px;padding:20px 0;'>no templates match your search</div>", unsafe_allow_html=True)
    else:
        for cat, items in display_templates.items():
            st.markdown(f"<div style='font-size:10px;color:#444;letter-spacing:0.08em;margin:16px 0 8px 0;text-transform:uppercase;'>{cat}</div>", unsafe_allow_html=True)
            cols = st.columns(2)
            for j, tmpl in enumerate(items):
                with cols[j % 2]:
                    # Build tag HTML
                    tag_html = "".join([f"<span class='tmpl-tag'>{t}</span>" for t in tmpl["tags"]])
                    st.markdown(f"""
                    <div class='tmpl-card'>
                        <div style='font-size:12px;color:#e8e8e8;font-weight:500;margin-bottom:6px;'>{tmpl["name"]}</div>
                        <div>{tag_html}</div>
                        <div style='font-size:11px;color:#333;margin-top:6px;line-height:1.5;'>
                            {tmpl["prompt"][:80]}{"..." if len(tmpl["prompt"]) > 80 else ""}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"USE  ↗", key=f"tmpl_{cat}_{j}", use_container_width=True):
                        st.session_state["tmpl_loaded"] = tmpl["prompt"]
                        st.rerun()

    st.divider()

    # ── Template editor ──────────────────────────────────────────────────────
    st.markdown("<div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:8px;'>TEMPLATE EDITOR</div>", unsafe_allow_html=True)

    loaded = st.session_state.get("tmpl_loaded", "")
    edited_tmpl = st.text_area(
        "Edit template — replace {placeholders} with your content",
        value=loaded,
        height=160,
        key="tmpl_editor",
        placeholder="select a template above or write your own prompt here...",
    )

    te_c1, te_c2, te_c3 = st.columns([2, 2, 1])
    with te_c1:
        if st.button("📤 SEND TO CHAT", use_container_width=True, key="tmpl_send"):
            if not edited_tmpl or not edited_tmpl.strip():
                st.warning("template is empty")
            else:
                st.session_state.messages.append({"role": "user", "content": edited_tmpl})
                st.session_state.total_messages += 1
                st.session_state["tmpl_loaded"] = ""
                save_current_session()
                st.success("✅ sent! switch to 💬 CHAT tab")
    with te_c2:
        if st.button("📋 COPY AS SYSTEM PROMPT", use_container_width=True, key="tmpl_sys"):
            if edited_tmpl and edited_tmpl.strip():
                st.session_state["sys_prompt_input"] = edited_tmpl
                st.toast("Set as system prompt! Open ⚙️ Settings to confirm.", icon="📋")
    with te_c3:
        if st.button("✕ CLEAR", use_container_width=True, key="tmpl_clear"):
            st.session_state["tmpl_loaded"] = ""
            st.rerun()

    st.divider()
    st.markdown(f"""
    <div style='font-size:10px;color:#222;line-height:1.9;'>
        <b style='color:#333;'>How to use:</b><br>
        1. Browse categories or search for a template<br>
        2. Click <b>USE ↗</b> to load it into the editor<br>
        3. Replace <code style='color:#3a3a3a;'>{{placeholders}}</code> with your actual content<br>
        4. Click <b>SEND TO CHAT</b> to use it as your next message<br>
        5. Or click <b>COPY AS SYSTEM PROMPT</b> to set it as the AI's persona
    </div>
    """, unsafe_allow_html=True)