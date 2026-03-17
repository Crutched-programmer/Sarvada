import streamlit as st
import requests
import time
import pandas as pd
import base64
import io
import json

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sarvam Agent",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SESSION STATE DEFAULTS ────────────────────────────────────────────────────
defaults = {
    "messages":        [],
    "total_messages":  0,
    "token_history":   [],
    "favourites":      [],
    "tts_audio":       None,
    "stt_result":      "",
    "show_settings":   False,
    "accent":          "#db5151",
    "cli_mode":        False,
    "memory_summary":  "",
    "last_summarised": 0,
    "search_query":      "",
    "translate_results":  {},
    "msg_translations":   {},
    "show_tr_picker":     {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

A  = st.session_state.accent        # base
AD = darken(A)                       # dark shade
AL = lighten(A)                      # light shade
AT = tint_bg(A, 0.12)               # very dark tint for sidebar
AT2= tint_bg(A, 0.18)               # slightly lighter tint

CLI = st.session_state.cli_mode

# ─── DYNAMIC CSS ───────────────────────────────────────────────────────────────
FONT = "'Courier New', monospace" if CLI else "'IBM Plex Mono', monospace"
MSG_RADIUS = "4px" if CLI else "16px"
BTN_RADIUS = "4px" if CLI else "24px"
INPUT_RADIUS = "4px" if CLI else "24px"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

*, html, body, [class*="css"] {{
    font-family: {FONT} !important;
    box-sizing: border-box;
}}

.stApp, .main, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"] {{
    background-color: #0a0a0a !important;
}}
.block-container {{
    padding-top: 1.5rem !important;
    max-width: 920px !important;
}}

/* SIDEBAR */
[data-testid="stSidebar"] {{
    background-color: {AT} !important;
    border-right: 1px solid {AT2} !important;
}}

[data-testid="stSidebar"] * {{ color: {AL} !important; }}

/* Fix sidebar collapse button always visible */
[data-testid="stSidebarCollapseButton"] {{
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}}
[data-testid="stSidebarCollapseButton"] svg {{
    fill: {A} !important;
}}

/* TEXT */
p, span, label, div, li, td, th, h1, h2, h3, h4 {{ color: #e8e8e8 !important; }}

/* CLI MODE BODY */
{"body { background: #000 !important; }" if CLI else ""}
{".stApp { background: #000 !important; }" if CLI else ""}

/* INPUTS */
input, textarea {{
    background-color: #0f0f0f !important;
    border: 1px solid #252525 !important;
    color: #e8e8e8 !important;
    border-radius: {INPUT_RADIUS} !important;
    transition: border-color 0.2s !important;
}}
input:focus, textarea:focus {{
    border-color: {A} !important;
    box-shadow: 0 0 0 2px {alpha(A, 0.15)} !important;
    outline: none !important;
}}

/* BUTTONS */
.stButton > button {{
    background-color: #0f0f0f !important;
    border: 1px solid #252525 !important;
    color: #888 !important;
    border-radius: {BTN_RADIUS} !important;
    font-size: 12px !important;
    letter-spacing: {"0.1em" if CLI else "0.05em"} !important;
    transition: all 0.18s ease !important;
    padding: 6px 16px !important;
    {"text-transform: uppercase;" if CLI else ""}
}}
.stButton > button:hover {{
    background-color: {A} !important;
    border-color: {A} !important;
    color: #000 !important;
    transform: {"none" if CLI else "translateY(-1px)"} !important;
    box-shadow: 0 4px 16px {alpha(A, 0.3)} !important;
    {"letter-spacing: 0.15em !important;" if CLI else ""}
}}
.stButton > button:active {{ transform: none !important; }}

.stDownloadButton > button {{
    background-color: #0f0f0f !important;
    border: 1px solid #252525 !important;
    color: #888 !important;
    border-radius: {BTN_RADIUS} !important;
    font-size: 12px !important;
    transition: all 0.18s ease !important;
}}
.stDownloadButton > button:hover {{
    background-color: {A} !important;
    border-color: {A} !important;
    color: #000 !important;
    box-shadow: 0 4px 16px {alpha(A, 0.3)} !important;
}}

/* SELECTBOX */
[data-testid="stSelectbox"] > div > div {{
    background-color: #0f0f0f !important;
    border: 1px solid #252525 !important;
    border-radius: {BTN_RADIUS} !important;
    color: #888 !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stSelectbox"] > div > div:hover {{ border-color: {A} !important; }}

/* EXPANDER */
[data-testid="stExpander"] {{
    background-color: #0f0f0f !important;
    border: 1px solid #1e1e1e !important;
    border-radius: {"4px" if CLI else "16px"} !important;
}}
[data-testid="stExpander"] summary {{ color: #666 !important; letter-spacing: 0.04em !important; }}

/* METRICS */
[data-testid="stMetric"] {{
    background: #0f0f0f !important;
    border: 1px solid #1a1a1a !important;
    border-radius: {"4px" if CLI else "16px"} !important;
    padding: 12px !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stMetric"]:hover {{ border-color: {AT2} !important; }}
[data-testid="stMetricValue"] {{ color: {AL} !important; font-size: 1.4rem !important; }}
[data-testid="stMetricLabel"] {{ color: #444 !important; font-size: 10px !important; letter-spacing: 0.06em !important; }}

/* DIVIDER */
hr {{ border-color: #1a1a1a !important; opacity: 1 !important; }}

/* CHAT MESSAGES */
[data-testid="stChatMessage"] {{
    background-color: {"#000" if CLI else "#0a0a0a"} !important;
    border-radius: {MSG_RADIUS} !important;
    padding: 8px 4px !important;
    animation: fadeSlideIn 0.22s ease forwards;
    {"border-left: 2px solid #1a1a1a !important;" if CLI else ""}
}}

/* CHAT INPUT */
[data-testid="stChatInput"] {{
    background-color: #0f0f0f !important;
    border: 1px solid #252525 !important;
    border-radius: {INPUT_RADIUS} !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {A} !important;
    box-shadow: 0 0 0 2px {alpha(A, 0.12)} !important;
}}
[data-testid="stChatInputTextArea"] {{
    color: #e8e8e8 !important;
    background: transparent !important;
}}

/* ALERT */
[data-testid="stAlert"] {{
    background-color: {AT} !important;
    border: 1px solid {AT2} !important;
    border-radius: {"4px" if CLI else "12px"} !important;
    color: {AL} !important;
}}

/* TABS */
[data-testid="stTabs"] [role="tab"] {{
    color: #333 !important;
    font-size: 11px !important;
    letter-spacing: 0.07em !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    padding: 8px 16px !important;
    transition: color 0.2s !important;
    text-transform: uppercase !important;
}}
[data-testid="stTabs"] [role="tab"]:hover {{ color: {AL} !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: {A} !important;
    border-bottom: 2px solid {A} !important;
}}
[data-testid="stTabs"] [role="tablist"] {{ border-bottom: 1px solid #1a1a1a !important; }}

/* FILE UPLOADER */
[data-testid="stFileUploader"] {{
    background-color: #0f0f0f !important;
    border: 1px dashed #252525 !important;
    border-radius: {"4px" if CLI else "16px"} !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stFileUploader"]:hover {{ border-color: {A} !important; }}

/* SCROLLBAR */
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-track {{ background: #0a0a0a; }}
::-webkit-scrollbar-thumb {{ background: {AT2}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {A}; }}

.stCaption {{ color: #2e2e2e !important; font-size: 11px !important; }}
#MainMenu, footer, header {{ visibility: hidden; }}

/* ANIMATIONS */
@keyframes fadeSlideIn {{
    from {{ opacity: 0; transform: translateY({"0" if CLI else "6px"}); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }} to {{ opacity: 1; }}
}}
@keyframes blink {{
    0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }}
}}

/* CLI CURSOR BLINK on active chat */
{"" if not CLI else """
[data-testid="stChatInputTextArea"]::after {
    content: '█';
    animation: blink 1s step-end infinite;
    color: """ + A + """;
}
"""}

/* TOKEN BAR */
.token-bar-wrap {{
    background: #111;
    border: 1px solid #1a1a1a;
    border-radius: 6px;
    height: 4px;
    width: 100%;
    margin-top: 4px;
    overflow: hidden;
}}
.token-bar-fill {{
    height: 4px;
    border-radius: 6px;
    transition: width 0.3s ease;
}}

/* SETTINGS MODAL */
.settings-panel {{
    background: #0f0f0f;
    border: 1px solid #1e1e1e;
    border-radius: {"4px" if CLI else "20px"};
    padding: 28px;
    margin-bottom: 16px;
    animation: fadeIn 0.2s ease;
}}
.settings-title {{
    font-size: 11px;
    letter-spacing: 0.12em;
    color: #444;
    text-transform: uppercase;
    margin-bottom: 20px;
}}

/* CLI PROMPT PREFIX */
.cli-prompt {{
    color: {A};
    font-size: 12px;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}}

[data-testid="stSidebarCollapseButton"] {{
    display: none !important;
}}
[data-testid="collapsedControl"] {{
    display: none !important;
}}
section[data-testid="stSidebar"] {{
    min-width: 260px !important;
    max-width: 260px !important;
    transform: none !important;
    visibility: visible !important;
}}

/* MEMORY BADGE */
.memory-badge {{
    display: inline-block;
    background: {AT};
    border: 1px solid {AT2};
    border-radius: {"2px" if CLI else "20px"};
    color: {AL};
    font-size: 10px;
    padding: 2px 10px;
    letter-spacing: 0.06em;
    margin-bottom: 12px;
}}

/* COLOUR SWATCH BUTTONS */
.swatch-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0; }}
.swatch {{
    width: 28px; height: 28px;
    border-radius: {"2px" if CLI else "50%"};
    cursor: pointer;
    border: 2px solid transparent;
    transition: transform 0.15s, border-color 0.15s;
    display: inline-block;
}}
.swatch:hover {{ transform: scale(1.15); }}

code, pre {{
    background-color: #111 !important;
    border: 1px solid #1e1e1e !important;
    border-radius: {"2px" if CLI else "8px"} !important;
    color: {AL} !important;
}}

audio {{
    filter: invert(1) hue-rotate(160deg) !important;
    border-radius: {BTN_RADIUS} !important;
    width: 100% !important;
}}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTS ─────────────────────────────────────────────────────────────────
SARVAM_BASE = "https://api.sarvam.ai/v1"

PRESET_PROMPTS = {
    "🤖 Default":      "You are a helpful, concise AI assistant. Always format your responses using HTML tags only — never use markdown syntax like ** or ##. Use <b> for bold, <i> for italic, <br> for line breaks, <ul><li> for lists, <table border='1'> for tables, <code> for inline code, <pre><code> for code blocks. Do not wrap responses in ```html``` blocks, just output raw HTML directly.",
    "💻 Coder":        "You are an expert programmer. Always format responses in HTML. Use <pre><code> for all code blocks, <b> for key terms, <br> for spacing. Never use markdown.",
    "🎓 Tutor":        "You are a patient tutor. Format all responses in HTML using <b> for key concepts, <ul><li> for steps, <br> for spacing. Never use markdown.",
    "✍️ Writer":       "You are a creative writing assistant. Format responses in HTML using <b>, <i>, <br> tags. Never use markdown.",
    "🔬 Researcher":   "You are a research assistant. Format responses in HTML using <b>, <ul><li>, <table> for structured data. Never use markdown.",
    "😂 Comedian":     "You are a witty AI. Format responses in HTML using <b> and <i> for emphasis. Never use markdown.",
}

ACCENT_PRESETS = [
    ("#db5151", "Red"),
    ("#5191db", "Blue"),
    ("#51db8a", "Green"),
    ("#db9f51", "Amber"),
    ("#9b51db", "Purple"),
    ("#51d4db", "Cyan"),
    ("#db5192", "Pink"),
    ("#dbcb51", "Yellow"),
]

LANG_CODES = {
    "English": "en-IN", "Hindi": "hi-IN", "Tamil": "ta-IN",
    "Telugu": "te-IN", "Kannada": "kn-IN", "Malayalam": "ml-IN",
}

SUGGESTIONS = [
    {"icon": "✍️", "title": "WRITE",      "prompt": "Write a short poem about the monsoon season in India"},
    {"icon": "🧠", "title": "EXPLAIN",    "prompt": "Explain quantum entanglement like I'm 15 years old"},
    {"icon": "🐛", "title": "DEBUG",      "prompt": "What's wrong with this Python code: `print('hello'`"},
    {"icon": "💡", "title": "BRAINSTORM", "prompt": "Give me 5 unique startup ideas for 2025 in the AI space"},
]

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

import re

def strip_tags(text: str) -> str:
    # Remove <think>...</think> blocks entirely (including content)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Remove all remaining HTML/XML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Clean up extra whitespace
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
    """Compress conversation into a short memory string — no system role."""
    history = "\n".join([
        f"{m['role'].upper()}: {m['content'][:300]}"
        for m in messages[-20:]
        if m.get("content", "").strip()
    ])
    if not history.strip():
        return ""
    payload = [
        {"role": "user", "content": (
            "Summarise this conversation in under 120 words. "
            "Focus on key facts, topics discussed, and user preferences. Be terse.\n\n"
            + history
        )},
    ]
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

# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style='padding:8px 0 4px 0;'>
        <div style='font-size:1rem;font-weight:600;color:{A};letter-spacing:0.1em;'>
            {">>> SARVAM AGENT" if CLI else "SARVAM AGENT"}
        </div>
        <div style='font-size:10px;color:#333;margin-top:2px;letter-spacing:0.06em;'>
            {"[CLI MODE ACTIVE]" if CLI else "powered by sarvam ai"}
        </div>
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

    c1, c2 = st.columns(2)
    with c1: st.metric("MSGS",  st.session_state.total_messages)
    with c2: st.metric("TURNS", len(st.session_state.messages) // 2)

    if st.session_state.token_history:
        st.metric("LAST TOK", st.session_state.token_history[-1]["Tokens"])

    st.divider()

    if st.button("NEW CHAT" if not CLI else "[ NEW CHAT ]", use_container_width=True):
        st.session_state.messages       = []
        st.session_state.token_history  = []
        st.session_state.tts_audio      = None
        st.session_state.memory_summary = ""
        st.session_state.last_summarised= 0
        st.rerun()

    if st.session_state.messages:
        chat_export = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
        st.download_button("EXPORT CHAT", data=chat_export, file_name="chat.txt", mime="text/plain", use_container_width=True)

    if st.session_state.favourites:
        fav_export = "\n\n---\n\n".join(st.session_state.favourites)
        st.download_button("EXPORT FAVS ⭐", data=fav_export, file_name="favs.txt", mime="text/plain", use_container_width=True)

    st.divider()
    st.caption(f"{'ibm plex mono' if not CLI else 'courier new'} · {A}")

# ─── SETTINGS MODAL (popout panel at top of main area) ─────────────────────────
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
        with sc3: stream_mode = st.toggle("STREAMING", value=True,   key="stream_t")
        with sc4: tts_enabled = st.toggle("AUTO TEXT-TO-SPEECH", value=True,  key="tts_t")

        tts_lang = st.selectbox("TTS LANGUAGE", list(LANG_CODES.keys()), index=list(LANG_CODES.keys()).index("Hindi"), key="tts_l")
        stt_lang = st.selectbox("MIC LANGUAGE", list(LANG_CODES.keys()), key="stt_l")

    with col_r:
        st.markdown("<div style='font-size:11px;color:#444;letter-spacing:0.06em;margin-bottom:6px;'>ACCENT COLOUR</div>", unsafe_allow_html=True)

        # Preset swatches
        swatch_html = "<div class='swatch-row'>"
        for hex_val, name in ACCENT_PRESETS:
            border = f"border-color:{hex_val}" if hex_val == st.session_state.accent else "border-color:#222"
            swatch_html += f"<div class='swatch' style='background:{hex_val};{border};' title='{name}'></div>"
        swatch_html += "</div>"
        st.markdown(swatch_html, unsafe_allow_html=True)

        # Clickable buttons for colour selection
        swatch_cols = st.columns(len(ACCENT_PRESETS))
        for i, (hex_val, name) in enumerate(ACCENT_PRESETS):
            with swatch_cols[i]:
                if st.button("●", key=f"sw_{i}", help=name):
                    st.session_state.accent = hex_val
                    st.rerun()

        # Custom hex input
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
                root@sarvam:~$<br>
                &gt; monospace font<br>
                &gt; sharp corners<br>
                &gt; uppercase labels<br>
                &gt; terminal aesthetic
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

# Pull settings with safe fallbacks — always defined regardless of settings panel state
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
tab_chat, tab_memory, tab_translate, tab_search, tab_voice, tab_upload, tab_stats, tab_favs = st.tabs([
    "💬  CHAT", "🧠  MEMORY", "🌐  TRANSLATE", "🔍  SEARCH", "🎤  VOICE", "📁  UPLOAD", "📊  STATS", "⭐  FAVS"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

    # Memory badge
    if st.session_state.memory_summary:
        st.markdown(f"<div class='memory-badge'>🧠 MEMORY ACTIVE — {len(st.session_state.memory_summary.split())} words compressed</div>", unsafe_allow_html=True)

    if not st.session_state.messages:
        prefix = "root@sarvam:~$ " if CLI else ""
        st.markdown(f"""
        <div style='padding:50px 0 24px 0;animation:fadeIn 0.4s ease;'>
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
                    st.markdown(msg["content"], unsafe_allow_html=True)
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    if CLI:
                        st.markdown(f"<div class='cli-prompt'>&gt;&gt; sarvam-m output:</div>", unsafe_allow_html=True)

                    # ── ENGLISH (original) ──────────────────────────────────
                    st.markdown(msg["content"].replace("\\n", "\n"), unsafe_allow_html=True)

                    # Action buttons row for English
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

                    # ── TRANSLATE LANGUAGE PICKER ───────────────────────────
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
                                                api_key,
                                                strip_tags(msg["content"]),
                                                "en-IN",
                                                LANG_CODES[pick_lang],
                                            )
                                            st.session_state.msg_translations[idx] = {
                                                "lang": pick_lang,
                                                "text": translated,
                                            }
                                            st.session_state.show_tr_picker[idx] = False
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"translate error: {e}")
                        with pk3:
                            if st.button("✕", key=f"tr_close_{idx}", use_container_width=True):
                                st.session_state.show_tr_picker[idx] = False
                                st.rerun()

                    # ── TRANSLATED VERSION (if exists) ──────────────────────
                    if idx in st.session_state.msg_translations:
                        tr = st.session_state.msg_translations[idx]
                        st.markdown(f"""
                        <div style='background:#0f0f0f;border:1px solid #1e1e1e;
                                    border-left:3px solid {A};border-radius:12px;
                                    padding:14px 16px;margin-top:8px;'>
                            <div style='font-size:10px;color:#444;letter-spacing:0.06em;margin-bottom:8px;'>
                                🌐 {tr["lang"].upper()}
                            </div>
                            <div style='font-size:14px;color:#e8e8e8;line-height:1.7;'>
                                {tr["text"]}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Action buttons row for translated version
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

    if st.session_state.tts_audio:
        autoplay_audio(st.session_state.tts_audio)
        st.session_state.tts_audio = None

    # Token bar slot
    counter_slot = st.empty()

    if prompt := st.chat_input("message..." if not CLI else "root@sarvam:~$ ", key="chat_input"):
        if not api_key:
            st.warning("⚠️ paste your api key in the sidebar first")
            st.stop()

        tok = count_tokens_approx(prompt)
        pct = min(tok / max_tokens * 100, 100)
        bar_col = AL if pct < 60 else A if pct < 90 else AD
        counter_slot.markdown(f"""
        <div style='font-size:10px;color:#333;margin-bottom:4px;letter-spacing:0.04em;'>~{tok} tokens</div>
        <div class='token-bar-wrap'><div class='token-bar-fill' style='width:{pct}%;background:{bar_col};'></div></div>
        """, unsafe_allow_html=True)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.total_messages += 1

        with st.chat_message("user", avatar="👤"):
            if CLI: st.markdown(f"<div class='cli-prompt'>user@sarvam:~$</div>", unsafe_allow_html=True)
            st.markdown(prompt)

        # Build payload — inject memory cleanly into system prompt
        if st.session_state.memory_summary:
            sys_content = f"{system_prompt}\n\nContext from earlier in this conversation:\n{st.session_state.memory_summary}"
        else:
            sys_content = system_prompt

        # Prepend system content as first user/assistant exchange (Sarvam rejects system role)
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
            with st.spinner("" if not CLI else "processing..."):
                try:
                    data  = call_sarvam_chat(api_key, model, messages_payload, max_tokens, temperature)
                    reply = data["choices"][0]["message"]["content"]

                    usage = data.get("usage", {})
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
                                placeholder.markdown(displayed + ("█" if CLI else "▌"), unsafe_allow_html=True)
                                time.sleep(0.007)
                        placeholder.markdown(reply.replace("\\n", "\n"), unsafe_allow_html=True)
                    else:
                        placeholder.markdown(reply.replace("\\n", "\n"), unsafe_allow_html=True)

                    if tts_enabled and api_key:
                        try:
                            ab = call_sarvam_tts(api_key, reply, LANG_CODES.get(tts_lang, "en-IN"))
                            if ab: st.session_state.tts_audio = ab
                        except: pass

                    # Auto memory summarise every N turns
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
                    result = call_sarvam_translate(
                        api_key, tr_text,
                        LANG_CODES[tr_source],
                        LANG_CODES[tr_target],
                    )
                    st.session_state.translate_results["last"] = {
                        "original": tr_text,
                        "translated": result,
                        "from": tr_source,
                        "to": tr_target,
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
                # Highlight search term
                raw = strip_tags(msg["content"])
                highlighted = raw.replace(
                    search_q,
                    f"<mark style='background:{A};color:#000;padding:0 2px;border-radius:3px;'>{search_q}</mark>"
                )
                # Case-insensitive highlight
                import re as _re
                highlighted = _re.sub(
                    f"({_re.escape(search_q)})",
                    f"<mark style='background:{A};color:#000;padding:0 2px;border-radius:3px;'>\1</mark>",
                    raw, flags=_re.IGNORECASE
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

    voice_lang = st.selectbox("TRANSCRIPTION LANGUAGE", list(LANG_CODES.keys()), key="voice_lang_tab")
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
