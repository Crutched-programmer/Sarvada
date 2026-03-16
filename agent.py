from nicegui import ui
import requests

SARVAM_API_KEY = "sk_v13x3ob5_TslaNd4aDKiufotX6jVHezQA"

API_URL = "https://api.sarvam.ai/v1/chat/completions"

messages = []

def send_message():
    user_text = user_input.value
    if not user_text:
        return

    chat_area.push(f"You: {user_text}")
    messages.append({"role": "user", "content": user_text})
    user_input.value = ""

    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {SARVAM_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "sarvam-m",
            "messages": messages
        }
    )

    data = response.json()
    reply = data["choices"][0]["message"]["content"]

    messages.append({"role": "assistant", "content": reply})
    chat_area.push(f"AI: {reply}")

ui.label("Sarvam AI Chatbot")

chat_area = ui.log().classes("w-full h-80")

user_input = ui.input(placeholder="Ask something...").classes("w-full")

ui.button("Send", on_click=send_message)

ui.run()