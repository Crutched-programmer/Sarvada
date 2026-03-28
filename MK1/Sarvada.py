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
    "cmd_result":         None,        # stores result of last inline command
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

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

*, html, body, [class*="css"] {{
    font-family: {FONT} !important;
    box-sizing: border-box;
}}

/* ── BACKGROUND — deep matte with subtle grain ── */
.stApp, .main, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"] {{
    background: #080810 !important;
}}
.block-container {{
    padding-top: 1.2rem !important;
    max-width: 900px !important;
}}

/* ── SIDEBAR — frosted glass panel ── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg,
        rgba(15,15,22,0.97) 0%,
        rgba(10,10,16,0.99) 100%) !important;
    border-right: 1px solid {alpha(A, 0.12)} !important;
    box-shadow: 4px 0 32px {alpha(A, 0.06)} !important;
}}
[data-testid="stSidebar"] * {{ color: #c8c8d8 !important; }}
[data-testid="stSidebar"]::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, {A}, transparent);
    opacity: 0.6;
}}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
[data-testid="collapsedControl"]        {{ display: none !important; }}
section[data-testid="stSidebar"] {{
    min-width: 260px !important;
    max-width: 260px !important;
    transform: none !important;
    visibility: visible !important;
}}

/* ── TEXT ── */
p, span, label, div, li, td, th, h1, h2, h3, h4 {{ color: #dddde8 !important; }}

{"body {{ background: #000 !important; }}" if CLI else ""}
{".stApp {{ background: #000 !important; }}" if CLI else ""}

/* ── INPUTS — glass inset ── */
input, textarea {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #e8e8f0 !important;
    border-radius: {INPUT_RADIUS} !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    backdrop-filter: blur(4px) !important;
}}
input:focus, textarea:focus {{
    border-color: {alpha(A, 0.5)} !important;
    box-shadow: 0 0 0 3px {alpha(A, 0.10)}, inset 0 1px 0 {alpha(A, 0.05)} !important;
    outline: none !important;
    background: rgba(255,255,255,0.05) !important;
}}

/* ── BUTTONS — ghost glass ── */
.stButton > button {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #888 !important;
    border-radius: {BTN_RADIUS} !important;
    font-size: 11px !important;
    letter-spacing: {"0.1em" if CLI else "0.06em"} !important;
    transition: all 0.18s ease !important;
    padding: 6px 14px !important;
    backdrop-filter: blur(4px) !important;
    {"text-transform: uppercase;" if CLI else ""}
}}
.stButton > button:hover {{
    background: {alpha(A, 0.15)} !important;
    border-color: {alpha(A, 0.4)} !important;
    color: {AL} !important;
    transform: {"none" if CLI else "translateY(-1px)"} !important;
    box-shadow: 0 4px 20px {alpha(A, 0.2)}, inset 0 1px 0 {alpha(A, 0.1)} !important;
}}
.stButton > button:active {{ transform: none !important; box-shadow: none !important; }}

.stDownloadButton > button {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #666 !important;
    border-radius: {BTN_RADIUS} !important;
    font-size: 11px !important;
    transition: all 0.18s ease !important;
}}
.stDownloadButton > button:hover {{
    background: {alpha(A, 0.15)} !important;
    border-color: {alpha(A, 0.4)} !important;
    color: {AL} !important;
    box-shadow: 0 4px 20px {alpha(A, 0.2)} !important;
}}

/* ── SELECTBOX ── */
[data-testid="stSelectbox"] > div > div {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: {BTN_RADIUS} !important;
    color: #888 !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stSelectbox"] > div > div:hover {{ border-color: {alpha(A, 0.35)} !important; }}

/* ── EXPANDER ── */
[data-testid="stExpander"] {{
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: {"4px" if CLI else "14px"} !important;
    backdrop-filter: blur(8px) !important;
}}
[data-testid="stExpander"] summary {{ color: #555 !important; letter-spacing: 0.04em !important; }}

/* ── METRICS — glass cards ── */
[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: {"4px" if CLI else "14px"} !important;
    padding: 12px 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    backdrop-filter: blur(8px) !important;
}}
[data-testid="stMetric"]:hover {{
    border-color: {alpha(A, 0.25)} !important;
    box-shadow: 0 0 16px {alpha(A, 0.08)} !important;
}}
[data-testid="stMetricValue"] {{ color: {AL} !important; font-size: 1.3rem !important; }}
[data-testid="stMetricLabel"] {{ color: #3a3a4a !important; font-size: 10px !important; letter-spacing: 0.07em !important; }}

/* ── DIVIDER ── */
hr {{ border-color: rgba(255,255,255,0.05) !important; opacity: 1 !important; }}

/* ── CHAT MESSAGES — glass bubbles ── */
[data-testid="stChatMessage"] {{
    background: transparent !important;
    border-radius: 0 !important;
    padding: 4px 0 !important;
    animation: fadeSlideIn 0.25s cubic-bezier(0.16,1,0.3,1) forwards;
}}

/* User bubble */
[data-testid="stChatMessage"][data-testid*="user"],
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    background: transparent !important;
}}
.user-bubble {{
    background: linear-gradient(135deg, {alpha(A, 0.12)} 0%, {alpha(A, 0.06)} 100%);
    border: 1px solid {alpha(A, 0.2)};
    border-radius: {"4px" if CLI else "18px 18px 6px 18px"};
    padding: 12px 16px;
    margin: 2px 0 2px 20%;
    line-height: 1.65;
    font-size: 13px;
    color: #e8e8f0;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 12px {alpha(A, 0.08)};
    word-break: break-word;
}}

/* Assistant bubble */
.assistant-bubble {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: {"4px" if CLI else "18px 18px 18px 6px"};
    padding: 14px 18px;
    margin: 2px 20% 2px 0;
    line-height: 1.75;
    font-size: 13.5px;
    color: #dddde8;
    backdrop-filter: blur(12px);
    box-shadow: 0 2px 16px rgba(0,0,0,0.3);
    word-break: break-word;
}}
.assistant-bubble:hover {{
    border-color: rgba(255,255,255,0.10);
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}}

/* ── CHAT INPUT — elevated glass ── */
[data-testid="stChatInput"] {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: {INPUT_RADIUS} !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    backdrop-filter: blur(12px) !important;
    box-shadow: 0 -2px 20px rgba(0,0,0,0.3) !important;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {alpha(A, 0.45)} !important;
    box-shadow: 0 0 0 3px {alpha(A, 0.08)}, 0 -2px 20px rgba(0,0,0,0.4) !important;
}}
[data-testid="stChatInputTextArea"] {{
    color: #e8e8f0 !important;
    background: transparent !important;
}}

/* ── ALERT ── */
[data-testid="stAlert"] {{
    background: {alpha(A, 0.07)} !important;
    border: 1px solid {alpha(A, 0.18)} !important;
    border-radius: {"4px" if CLI else "12px"} !important;
    color: {AL} !important;
    backdrop-filter: blur(8px) !important;
}}

/* ── TABS ── */
[data-testid="stTabs"] [role="tab"] {{
    color: #2e2e3e !important;
    font-size: 10px !important;
    letter-spacing: 0.08em !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    padding: 8px 14px !important;
    transition: color 0.2s !important;
    text-transform: uppercase !important;
}}
[data-testid="stTabs"] [role="tab"]:hover {{ color: #666 !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: {A} !important;
    border-bottom: 2px solid {A} !important;
    text-shadow: 0 0 12px {alpha(A, 0.4)};
}}
[data-testid="stTabs"] [role="tablist"] {{ border-bottom: 1px solid rgba(255,255,255,0.05) !important; }}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {{
    background: rgba(255,255,255,0.02) !important;
    border: 1px dashed rgba(255,255,255,0.10) !important;
    border-radius: {"4px" if CLI else "14px"} !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stFileUploader"]:hover {{ border-color: {alpha(A, 0.35)} !important; }}

/* ── SCROLLBAR ── */
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.06); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {alpha(A, 0.4)}; }}

.stCaption {{ color: #2a2a3a !important; font-size: 11px !important; }}
#MainMenu, footer, header {{ visibility: hidden; }}

/* ── ANIMATIONS ── */
@keyframes fadeSlideIn {{
    from {{ opacity: 0; transform: translateY({"0" if CLI else "8px"}) scale(0.99); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }} to {{ opacity: 1; }}
}}
@keyframes blink {{
    0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }}
}}

{"" if not CLI else """
[data-testid="stChatInputTextArea"]::after {
    content: '█';
    animation: blink 1s step-end infinite;
    color: """ + A + """;
}
"""}

/* ── SHIMMER — loading skeleton for API calls ── */
@keyframes shimmer {{
    0%   {{ background-position: -600px 0; }}
    100% {{ background-position: 600px 0; }}
}}
.shimmer-box {{
    border-radius: {"4px" if CLI else "14px"};
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.03) 0px,
        rgba(255,255,255,0.07) 160px,
        rgba(255,255,255,0.03) 320px
    );
    background-size: 600px 100%;
    animation: shimmer 1.4s ease-in-out infinite;
    border: 1px solid rgba(255,255,255,0.05);
}}
.shimmer-line {{
    height: 10px;
    border-radius: 6px;
    margin-bottom: 10px;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.03) 0px,
        rgba(255,255,255,0.08) 160px,
        rgba(255,255,255,0.03) 320px
    );
    background-size: 600px 100%;
    animation: shimmer 1.4s ease-in-out infinite;
}}
.shimmer-line.short {{ width: 55%; }}
.shimmer-line.medium {{ width: 78%; }}
.shimmer-line.long {{ width: 92%; }}

/* ── TOKEN BAR ── */
.token-bar-wrap {{
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    height: 3px;
    width: 100%;
    margin-top: 4px;
    overflow: hidden;
}}
.token-bar-fill {{
    height: 3px;
    border-radius: 6px;
    transition: width 0.4s cubic-bezier(0.16,1,0.3,1);
}}

/* ── SETTINGS PANEL — glass card ── */
.settings-panel {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {"4px" if CLI else "20px"};
    padding: 28px;
    margin-bottom: 16px;
    animation: fadeIn 0.2s ease;
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 40px rgba(0,0,0,0.4);
}}
.settings-title {{
    font-size: 10px;
    letter-spacing: 0.14em;
    color: #3a3a4a;
    text-transform: uppercase;
    margin-bottom: 20px;
}}

/* ── CLI PROMPT PREFIX ── */
.cli-prompt {{
    color: {A};
    font-size: 11px;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
    opacity: 0.7;
}}

/* ── MEMORY BADGE ── */
.memory-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: {alpha(A, 0.08)};
    border: 1px solid {alpha(A, 0.18)};
    border-radius: {"2px" if CLI else "20px"};
    color: {AL};
    font-size: 10px;
    padding: 3px 12px;
    letter-spacing: 0.06em;
    margin-bottom: 12px;
    backdrop-filter: blur(8px);
}}

/* ── SESSION ITEM ── */
.session-item {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: {"2px" if CLI else "10px"};
    padding: 6px 10px;
    margin-bottom: 4px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    font-size: 11px;
    letter-spacing: 0.04em;
}}
.session-item.active {{
    border-color: {alpha(A, 0.4)} !important;
    background: {alpha(A, 0.07)} !important;
    color: {AL} !important;
    box-shadow: 0 0 12px {alpha(A, 0.1)};
}}
.session-item:hover {{ border-color: {alpha(A, 0.2)}; }}

/* ── SWATCH BUTTONS ── */
.swatch-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0; }}
.swatch {{
    width: 26px; height: 26px;
    border-radius: {"2px" if CLI else "50%"};
    cursor: pointer;
    border: 2px solid transparent;
    transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
    display: inline-block;
}}
.swatch:hover {{ transform: scale(1.2); box-shadow: 0 0 10px currentColor; }}

/* ── CODE ── */
code, pre {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: {"2px" if CLI else "8px"} !important;
    color: {AL} !important;
}}

/* ── AUDIO ── */
audio {{
    filter: invert(0.85) hue-rotate(160deg) saturate(0.8) !important;
    border-radius: {BTN_RADIUS} !important;
    width: 100% !important;
    opacity: 0.8;
}}

/* ── TEMPLATE CARD ── */
.tmpl-card {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: {"4px" if CLI else "12px"};
    padding: 12px 14px;
    margin-bottom: 8px;
    transition: border-color 0.18s, box-shadow 0.18s;
    cursor: pointer;
    backdrop-filter: blur(8px);
}}
.tmpl-card:hover {{
    border-color: {alpha(A, 0.25)};
    box-shadow: 0 2px 16px {alpha(A, 0.08)};
}}
.tmpl-tag {{
    display: inline-block;
    background: {alpha(A, 0.08)};
    border: 1px solid {alpha(A, 0.15)};
    border-radius: {"2px" if CLI else "20px"};
    color: {alpha(A, 0.8)};
    font-size: 9px;
    padding: 1px 7px;
    letter-spacing: 0.06em;
    margin-right: 4px;
    margin-bottom: 4px;
}}

/* ── CMD RESULT BOX ── */
.cmd-result {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-left: 2px solid {A};
    border-radius: {"4px" if CLI else "12px"};
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 13px;
    line-height: 1.7;
    color: #dddde8;
    animation: fadeIn 0.2s ease;
    backdrop-filter: blur(8px);
}}
.cmd-label {{
    font-size: 10px;
    color: #3a3a4a;
    letter-spacing: 0.09em;
    margin-bottom: 8px;
    text-transform: uppercase;
}}

/* ── SIDEBAR BRAND GLOW ── */
.sidebar-brand {{
    padding: 6px 0 2px 0;
    position: relative;
}}
.sidebar-brand-name {{
    font-size: 0.9rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    color: {A};
    text-shadow: 0 0 20px {alpha(A, 0.5)};
}}
.sidebar-brand-sub {{
    font-size: 9px;
    color: #2a2a3a;
    margin-top: 2px;
    letter-spacing: 0.08em;
}}
.sidebar-section-label {{
    font-size: 9px;
    color: #2a2a3a;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    margin: 12px 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}
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
    ("#db5151", "Red"),   ("#5191db", "Blue"),  ("#51db8a", "Green"),
    ("#db9f51", "Amber"), ("#9b51db", "Purple"), ("#51d4db", "Cyan"),
    ("#db5192", "Pink"),  ("#dbcb51", "Yellow"),
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

# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class='sidebar-brand'>
        <div class='sidebar-brand-name'>{">>> SARVAM AGENT" if CLI else "◈ SARVAM AGENT"}</div>
        <div class='sidebar-brand-sub'>{"[CLI MODE ACTIVE]" if CLI else "powered by sarvam ai"}</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    api_key = st.text_input("API KEY", type="password", placeholder="paste key here...")
    model   = st.selectbox("MODEL", ["sarvam-m"])

    st.divider()

    # ── SETTINGS POPOUT BUTTON ──
    btn_label = "[ ⚙ SETTINGS ]" if CLI else "⚙️ Settings"
    if st.button(btn_label, use_container_width=True, key="toggle_settings"):
        st.session_state.show_settings = not st.session_state.show_settings

    st.divider()

    # ── FEATURE 10: CHAT SESSIONS PANEL ────────────────────────────────────────
    st.markdown(f"<div class='sidebar-section-label'>{'// SESSIONS' if CLI else 'Chat Sessions'}</div>", unsafe_allow_html=True)

    # New session button
    ns_col1, ns_col2 = st.columns([3, 1])
    with ns_col1:
        new_name = st.text_input("", placeholder="session name...", key="new_sess_name",
                                  label_visibility="collapsed")
    with ns_col2:
        if st.button("＋", key="add_session", help="New session"):
            save_current_session()
            sid = new_session(new_name.strip() if new_name.strip() else None)
            switch_session(sid)
            st.rerun()

    # List existing sessions
    for sid, sess in list(st.session_state.sessions.items()):
        is_active = (sid == st.session_state.active_session)
        border_col = A if is_active else "#1a1a1a"
        name_display = sess["name"]
        msg_count    = len(sess["messages"])

        sc1, sc2 = st.columns([5, 1])
        with sc1:
            if st.button(
                f"{'▶ ' if is_active else ''}{name_display} ({msg_count})",
                key=f"sess_btn_{sid}",
                use_container_width=True,
                help=f"Switch to {name_display}",
            ):
                if not is_active:
                    save_current_session()
                    switch_session(sid)
                    st.rerun()
        with sc2:
            if len(st.session_state.sessions) > 1:
                if st.button("✕", key=f"del_sess_{sid}", help="Delete session"):
                    if is_active:
                        # Switch to another session first
                        other = [k for k in st.session_state.sessions if k != sid]
                        if other:
                            switch_session(other[0])
                    del st.session_state.sessions[sid]
                    st.rerun()

    st.divider()

    c1, c2 = st.columns(2)
    with c1: st.metric("MSGS",  st.session_state.total_messages)
    with c2: st.metric("TURNS", len(st.session_state.messages) // 2)

    if st.session_state.token_history:
        st.metric("LAST TOK", st.session_state.token_history[-1]["Tokens"])

    st.divider()

    if st.button("NEW CHAT" if not CLI else "[ NEW CHAT ]", use_container_width=True):
        st.session_state.messages        = []
        st.session_state.token_history   = []
        st.session_state.tts_audio       = None
        st.session_state.memory_summary  = ""
        st.session_state.last_summarised = 0
        st.session_state.total_messages  = 0
        save_current_session()
        st.rerun()

    if st.session_state.messages:
        chat_export = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
        st.download_button("EXPORT CHAT", data=chat_export, file_name="chat.txt", mime="text/plain", use_container_width=True)

    if st.session_state.favourites:
        fav_export = "\n\n---\n\n".join(st.session_state.favourites)
        st.download_button("EXPORT FAVS ⭐", data=fav_export, file_name="favs.txt", mime="text/plain", use_container_width=True)

    st.divider()
    st.caption(f"{'ibm plex mono' if not CLI else 'courier new'} · {A}")

# ─── SETTINGS MODAL ────────────────────────────────────────────────────────────
if st.session_state.show_settings:
    st.markdown(f"<div class='settings-panel'>", unsafe_allow_html=True)
    st.markdown(f"<div class='settings-title'>{'// SETTINGS' if CLI else '⚙️  Settings'}</div>", unsafe_allow_html=True)

    col_l, col_r = st.columns([1.2, 1])

    with col_l:
        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>SYSTEM PROMPT PRESET</div>", unsafe_allow_html=True)
        preset_choice = st.selectbox("PRESET", list(PRESET_PROMPTS.keys()), label_visibility="collapsed", key="preset_sel")
        system_prompt = st.text_area("SYSTEM PROMPT", value=PRESET_PROMPTS[preset_choice], height=80, key="sys_prompt_input")

        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin:12px 0 6px 0;'>GENERATION</div>", unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)
        with sc1: temperature = st.slider("TEMP", 0.0, 1.0, 0.7, 0.05, key="temp_s")
        with sc2: max_tokens  = st.select_slider("TOKENS", [256, 512, 1024, 2048], value=1024, key="tok_s")

        sc3, sc4 = st.columns(2)
        with sc3: stream_mode = st.toggle("STREAMING",         value=True, key="stream_t")
        with sc4: tts_enabled = st.toggle("AUTO TEXT-TO-SPEECH", value=True, key="tts_t")

        tts_lang = st.selectbox("TTS LANGUAGE", list(LANG_CODES.keys()), index=list(LANG_CODES.keys()).index("Hindi"), key="tts_l")
        stt_lang = st.selectbox("MIC LANGUAGE", list(LANG_CODES.keys()), key="stt_l")

    with col_r:
        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>ACCENT COLOUR</div>", unsafe_allow_html=True)

        swatch_html = "<div class='swatch-row'>"
        for hex_val, name in ACCENT_PRESETS:
            border = f"border-color:{hex_val}" if hex_val == st.session_state.accent else "border-color:#222"
            swatch_html += f"<div class='swatch' style='background:{hex_val};{border};' title='{name}'></div>"
        swatch_html += "</div>"
        st.markdown(swatch_html, unsafe_allow_html=True)

        swatch_cols = st.columns(len(ACCENT_PRESETS))
        for i, (hex_val, name) in enumerate(ACCENT_PRESETS):
            with swatch_cols[i]:
                if st.button("●", key=f"sw_{i}", help=name):
                    st.session_state.accent = hex_val
                    st.rerun()

        custom_col = st.text_input("CUSTOM HEX", value=st.session_state.accent, key="custom_hex", max_chars=7)
        if st.button("APPLY COLOUR", key="apply_colour"):
            if custom_col and custom_col.startswith("#") and len(custom_col) == 7:
                st.session_state.accent = custom_col
                st.rerun()
            else:
                st.error("enter a valid hex like #a1b2c3")

        st.divider()

        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>INTERFACE MODE</div>", unsafe_allow_html=True)
        cli_toggle = st.toggle("⌨️ CLI MODE", value=st.session_state.cli_mode, key="cli_toggle")
        if cli_toggle != st.session_state.cli_mode:
            st.session_state.cli_mode = cli_toggle
            st.rerun()

        if CLI:
            st.markdown(f"""
            <div style='font-size:10px;color:#333;margin-top:8px;letter-spacing:0.05em;line-height:1.8;'>
                root@sarvam:~$<br>&gt; monospace font<br>&gt; sharp corners<br>
                &gt; uppercase labels<br>&gt; terminal aesthetic
            </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>MEMORY</div>", unsafe_allow_html=True)
        mem_auto = st.toggle("AUTO SUMMARISE every 10 turns", value=True, key="mem_auto")

    close_col, _ = st.columns([1, 4])
    with close_col:
        if st.button("✕ CLOSE SETTINGS", key="close_settings"):
            st.session_state.show_settings = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

# Pull settings with safe fallbacks
DEFAULT_PROMPT = PRESET_PROMPTS["🤖 Default"]
system_prompt = st.session_state.get("sys_prompt_input") or DEFAULT_PROMPT
temperature   = st.session_state.get("temp_s",   0.7)
max_tokens    = st.session_state.get("tok_s",    1024)
stream_mode   = st.session_state.get("stream_t", True)
tts_enabled   = st.session_state.get("tts_t",    True)
tts_lang      = st.session_state.get("tts_l",    "Hindi")
stt_lang      = st.session_state.get("stt_l",    "English")
mem_auto      = st.session_state.get("mem_auto", True)

# ─── TABS ──────────────────────────────────────────────────────────────────────
tab_chat, tab_memory, tab_translate, tab_search, tab_voice, tab_upload, tab_stats, tab_favs, tab_templates = st.tabs([
    "💬  CHAT", "🧠  MEMORY", "🌐  TRANSLATE", "🔍  SEARCH",
    "🎤  VOICE", "📁  UPLOAD", "📊  STATS", "⭐  FAVS", "📋  TEMPLATES"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

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
                {"add api key in sidebar → pick a prompt or type below" if not CLI else "[add api key] → [type command below]"}
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
with tab_memory:
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
with tab_translate:
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
with tab_search:
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
with tab_voice:
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
with tab_upload:
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
with tab_stats:
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
with tab_favs:
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
# TAB 9 — TEMPLATES  (Feature 15)
# ══════════════════════════════════════════════════════════════════════════════
with tab_templates:
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