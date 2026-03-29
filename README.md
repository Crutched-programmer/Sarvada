# Sarvada MK 3

A Streamlit-based chat interface powered by the Sarvam AI API. Sarvada provides a multi-session, feature-rich conversational agent with support for text-to-speech, speech-to-text, translation, memory compression, file uploads, prompt templates, and a set of inline slash commands — all in a single Python file.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Configuration](#configuration)
- [Interface Overview](#interface-overview)
- [Tabs](#tabs)
  - [Chat](#chat)
  - [Memory](#memory)
  - [Translate](#translate)
  - [Search](#search)
  - [Voice](#voice)
  - [Upload](#upload)
  - [Stats](#stats)
  - [Favourites](#favourites)
  - [Templates](#templates)
  - [Settings](#settings)
- [Inline Commands](#inline-commands)
- [Prompt Templates](#prompt-templates)
- [System Prompts](#system-prompts)
- [Session Management](#session-management)
- [Memory System](#memory-system)
- [TTS and STT](#tts-and-stt)
- [Translation](#translation)
- [API Reference](#api-reference)
- [Known Quirks](#known-quirks)

---

## Requirements

- Python 3.9 or later
- A Sarvam AI API key — obtain one from [sarvam.ai](https://sarvam.ai)

Python packages:

```
streamlit
requests
pandas
```

Install with:

```bash
pip install streamlit requests pandas
```

---

## Installation

Clone or download the repository, then place `Sarvada.py` in your working directory. No further setup is required beyond installing the dependencies above.

---

## Running the App

```bash
streamlit run Sarvada.py
```

Streamlit will open the app in your default browser at `http://localhost:8501`.

---

## Configuration

All configuration is done inside the app through the Settings tab. Nothing requires editing the source file. On first launch the app starts with empty defaults and waits for an API key before it will make any requests.

The only value you must provide is your Sarvam API key. Paste it into the API Key field in Settings and press Save. The key is stored in Streamlit session state for the duration of the browser session and is not persisted to disk.

---

## Interface Overview

The layout uses a collapsible left sidebar for navigation and a main content area that changes based on the active tab. The sidebar can be toggled between a full label view and a compact icon-only view using the arrow button at the bottom.

The sidebar contains:

- Navigation buttons for each tab
- The active session name and message count
- Controls to create, switch, and delete chat sessions
- A text input to name new sessions
- A button to export the current conversation as a plain text file
- A Settings button pinned to the bottom

The main area renders whichever tab is currently active.

---

## Tabs

### Chat

The primary tab. Displays the conversation history and a chat input at the bottom.

When no messages exist, the chat area shows four suggestion cards: Write, Explain, Debug, and Brainstorm. Clicking one loads its prompt into the input and sends it immediately.

Each assistant reply includes three action buttons beneath it:

- Star — saves the reply to your Favourites list
- Speaker — generates audio via TTS and autoplays it
- Globe — opens an inline language picker to translate that specific reply

Translations appear below the original reply in a styled block and can themselves be saved to Favourites or read aloud.

The chat input accepts inline slash commands (see [Inline Commands](#inline-commands)). Any input starting with `/` is intercepted and handled locally or via API before the next render.

The assistant reply goes through the following pipeline on each submission:

1. The user message is appended to the session message list
2. A fake user/assistant injection pair is prepended to satisfy the Sarvam API's requirement that the conversation not begin with a system role
3. If a memory summary exists it is injected into the system prompt
4. The full payload is sent to `https://api.sarvam.ai/v1/chat/completions`
5. The raw reply is stripped of any `<think>...</think>` blocks before display
6. If auto-TTS is enabled the stripped reply is sent to the TTS endpoint
7. Every ten turns, if auto-summarise is enabled, the conversation is compressed into a memory summary

The model used is `sarvam-m`. This is hardcoded and not configurable through the UI.

### Memory

Displays the current compressed memory summary if one exists. The summary is editable — changes are saved back to session state immediately. You can also manually trigger a summarisation of the current conversation without waiting for the ten-turn threshold, and clear the memory entirely.

The memory system is described in more detail under [Memory System](#memory-system).

### Translate

A standalone translation tool. Select a source language and a target language from the dropdowns, enter or paste text, and click Translate. The result appears below the input with options to send it directly to the Chat tab as a user message or read it aloud via TTS.

### Search

Searches the conversation history of the active session. Type a term and all matching messages are displayed with the search term highlighted. Results show the message index and whether the message was from the user or the assistant.

### Voice

Upload an audio file in `.wav`, `.mp3`, or `.ogg` format. The file is previewed with an audio player. Click Transcribe to send it to the Sarvam STT endpoint. The transcript appears in an editable text area and can be forwarded to the Chat tab as a user message.

### Upload

Upload a text file or image. Supported file types for text are `.txt`, `.py`, `.js`, `.json`, `.csv`, `.md`. Supported image formats are `.png`, `.jpg`, `.jpeg`. PDFs are also accepted but treated as binary and referenced by name only.

Text files are previewed with syntax highlighting up to the first 2000 characters. The full content (up to 3000 characters) is appended to an optional question you type and sent as a user message to the Chat tab.

Images are displayed as a preview. The filename is attached to your question and sent to the chat.

### Stats

Displays three metrics: total messages, number of turns (user/assistant pairs), and total word count across the session. Below the metrics, a bar chart shows token usage per turn if token history exists. A second pair of bar charts breaks down word count by message, separated into user messages and assistant messages.

### Favourites

Lists all responses that were starred from the Chat tab. Each entry is shown in an expandable section labelled with its index and word count. A Remove button deletes the entry from the list.

If any favourites exist, a Download button appears in the sidebar to export them all as a plain text file separated by horizontal rules.

### Templates

A library of 27 pre-written prompt templates organised across six categories: Email, Code, Writing, Analysis, Learning, and Productivity. A search box filters templates by name, content, or tag.

Clicking the Use button on any template loads it into the template editor at the bottom of the tab. You replace the `{placeholder}` values with your actual content, then either send the result to Chat as a user message or set it as the active system prompt.

### Settings

Controls all persistent preferences for the session:

- API Key — password input, saved with a Save button
- System Prompt — a dropdown of six presets with an editable text area to customise
- Temperature — slider from 0.0 to 1.0, default 0.7
- Max Tokens — select slider with options 256, 512, 1024, 2048, default 1024
- Streaming — toggle to enable character-by-character typewriter rendering
- Auto TTS — toggle to automatically read every assistant reply aloud
- TTS Language — the voice language used for text-to-speech
- Mic Language — the language used for speech-to-text transcription
- Auto-summarise Memory — toggle to compress memory every 10 turns
- Accent Colour — a colour picker with 8 presets
- Light Mode — toggle between dark and light themes
- CLI Mode — toggle that changes the font to Courier New and applies a terminal-style visual treatment

---

## Inline Commands

Type any of the following at the start of a chat message. The command is intercepted before it reaches the AI and handled separately. The result appears in a dismissable box above the chat input.

| Command | Behaviour |
|---|---|
| `/help` | Lists all available commands with descriptions |
| `/translate [language]` | Translates the last assistant reply to the specified language. Defaults to Hindi if no language is given or the name is not recognised |
| `/summarise` | Asks the model to summarise the full conversation in five bullet points |
| `/speak` | Generates TTS audio for the last assistant reply and autoplays it |
| `/clear` | Clears all messages, token history, and memory from the current session |
| `/stats` | Shows message count, turn count, word count, and last token usage inline |

Commands are matched case-insensitively. Unrecognised commands produce an error block with a suggestion to use `/help`.

---

## Prompt Templates

Templates use `{placeholder}` syntax. The template editor does not automatically validate or strip unfilled placeholders. If you send a template with `{topic}` still in it, the model will receive the literal text `{topic}`.

Template categories and counts:

| Category | Templates |
|---|---|
| Email | 4 |
| Code | 5 |
| Writing | 5 |
| Analysis | 4 |
| Learning | 4 |
| Productivity | 4 |

Templates can also be set as the system prompt using the "Copy as System Prompt" button in the editor, which writes the template text directly into the system prompt field in Settings.

---

## System Prompts

Six presets are available:

- Default — general assistant, HTML-formatted responses
- Coder — programmer persona, code blocks in `<pre><code>` tags
- Tutor — patient teaching persona, structured step-by-step formatting
- Writer — creative writing assistant
- Researcher — research and structured data persona
- Comedian — light-hearted and witty persona

All presets instruct the model to use HTML tags rather than markdown for formatting, since the chat renders responses with `unsafe_allow_html=True`. Responses are displayed inside styled `div` elements that interpret HTML.

---

## Session Management

Multiple named chat sessions can be active simultaneously within a single browser session. Each session maintains its own:

- Message history
- Token usage history
- Memory summary
- Auto-summarise cursor position
- Total message count

Sessions are stored in `st.session_state.sessions` as a dictionary keyed by an auto-incrementing integer. When you switch sessions, the current session's state is saved before loading the target session.

Sessions do not persist between browser refreshes. There is no file-based or database-backed storage.

---

## Memory System

When the number of conversation turns reaches a multiple of ten, Sarvada sends the last 20 messages to `sarvam-m` with an instruction to produce a summary under 120 words. This summary is stored as `memory_summary` in session state.

On subsequent requests, the summary is prepended to the system prompt as context so the model can reference earlier parts of the conversation even after those messages would have exceeded its effective context window.

The summary can be viewed and edited in the Memory tab. Edits are applied immediately to the in-memory state and will be injected into the next request.

Clearing the memory removes both the summary text and the cursor that tracks when the last summarisation occurred.

---

## TTS and STT

TTS uses the Sarvam Bulbul v3 model via `https://api.sarvam.ai/text-to-speech`. The voice is set to `shubh`. Text is stripped of all HTML tags before being sent, and is truncated at 2500 characters.

Audio is returned as a base64-encoded WAV and is autoplayed in the browser using a hidden `<audio>` element injected via `st.markdown`.

STT uses the Saarika v2 model via `https://api.sarvam.ai/speech-to-text`. Audio files are sent as multipart form data. The language code used for transcription is the one selected in the Voice tab's language dropdown.

Supported TTS and STT languages: English, Hindi, Tamil, Telugu, Kannada, Malayalam. All use Indian locale codes (`en-IN`, `hi-IN`, etc.).

---

## Translation

Translation uses `https://api.sarvam.ai/translate`. Requests are sent in formal mode with preprocessing enabled. Input is capped at 1000 characters per request.

The source language for per-message translations from the Chat tab is always assumed to be English (`en-IN`). The standalone Translate tab allows selecting any language as either source or target.

---

## API Reference

All requests use the header `api-subscription-key` for authentication. Timeouts are set to 30 seconds for chat and TTS endpoints and 20 seconds for translation and memory summarisation.

Endpoints used:

| Endpoint | Purpose |
|---|---|
| `POST /v1/chat/completions` | Chat completions and memory summarisation |
| `POST /text-to-speech` | Speech synthesis |
| `POST /speech-to-text` | Speech transcription |
| `POST /translate` | Text translation |

The Sarvam API rejects a `system` role at the start of the messages array. Sarvada works around this by prepending a fake user/assistant exchange that carries the system prompt content as a user message and acknowledges it as an assistant response.

---

## Known Quirks

The `<think>` block stripping uses a regex that handles both closed `<think>...</think>` tags and unclosed `<think>` tags that reach the end of the response. This is necessary because `sarvam-m` occasionally produces visible chain-of-thought output that would otherwise appear in the chat bubble.

Streaming mode is simulated. The API is called once and the full response is replayed character by character with a short sleep. The delay per character is calculated as `8000 / len(reply)` milliseconds, clamped between 4ms and 18ms, so shorter replies appear faster and longer replies do not take excessive time.

Token counts shown in the Stats tab and the per-message counter use the value returned in the `usage.total_tokens` field of the API response. The counter shown while typing is an approximation calculated as `word_count * 4 / 3`.
