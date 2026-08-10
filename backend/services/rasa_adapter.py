"""Flask <-> Rasa bridge.

Exposes POST /api/askivy/chat-rasa, which accepts the exact same request body as
the existing rule-based /api/askivy/chat and returns the exact same response
shape. That is the whole point: the React ChatWidget does not need to know which
engine answered.

Request   {"employeeId": "sarah", "message": "how many leave days do I have?"}
Response  {"text": ..., "source": ..., "isRecommendation": ...,
           "canSubmitLeave": ..., "suggestedLeave": ..., "thinkingSteps": [...]}

Flow of a single turn:
    ChatWidget -> this adapter -> Rasa REST channel (:5005)
                                   -> CompactLLMCommandGenerator asks Claude
                                      "what does the user want?"
                                   -> FlowPolicy runs the matching flow
                                   -> action server (:5055) calls back into
                                      this same Flask API for HRMS facts
               <- adapter merges Rasa's reply into the widget's JSON shape

The employee id is passed to Rasa as the `sender`, which makes it the
conversation id AND the identity the custom actions act on.
"""

import os

import requests
from flask import Blueprint, jsonify, request

from models import db, Employee, ChatMessage

rasa_bp = Blueprint("rasa", __name__)

RASA_URL = os.getenv("RASA_URL", "http://localhost:5005").rstrip("/")
RASA_TIMEOUT = float(os.getenv("RASA_TIMEOUT", "30"))

FALLBACK_TEXT = (
    "AskIvy's reasoning service didn't return an answer for that. "
    "Try rephrasing, or ask about leave balance, applying for leave, "
    "compassionate leave, parental leave, or a specific HR policy."
)
UNREACHABLE_TEXT = (
    "I can't reach AskIvy's reasoning service right now. Make sure the Rasa "
    "server is running on port 5005, then try again."
)


def _blank_answer(text):
    return {
        "text": text,
        "source": None,
        "isRecommendation": False,
        "canSubmitLeave": False,
        "suggestedLeave": None,
        "thinkingSteps": [],
        "buttons": [],
    }


def _merge_rasa_messages(messages):
    """Collapse Rasa's list of REST messages into one ChatWidget payload.

    Rasa returns a list like:
        [{"recipient_id": "sarah", "text": "You have 12 days..."},
         {"recipient_id": "sarah", "custom": {"askivy": {...metadata...}}}]

    Text parts are joined in order; the last "askivy" metadata block wins. A
    flow that only utters a domain response (no custom action) still works —
    it just carries no metadata, which is exactly the neutral default.

    Buttons ride on the message that offers them (Rasa's own collect steps and
    default patterns emit these). The last set wins, since that is the choice
    the user is actually being asked to make.
    """
    texts = []
    metadata = {}
    buttons = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        text = message.get("text")
        if text:
            texts.append(str(text).strip())
        custom = message.get("custom") or {}
        if isinstance(custom, dict) and isinstance(custom.get("askivy"), dict):
            metadata = custom["askivy"]
        if isinstance(message.get("buttons"), list) and message["buttons"]:
            buttons = message["buttons"]

    answer = _blank_answer("\n\n".join(t for t in texts if t) or FALLBACK_TEXT)
    answer.update({
        "source": metadata.get("source") or None,
        "isRecommendation": bool(metadata.get("isRecommendation", False)),
        "canSubmitLeave": bool(metadata.get("canSubmitLeave", False)),
        "suggestedLeave": metadata.get("suggestedLeave") or None,
        "thinkingSteps": metadata.get("thinkingSteps") or [],
        "buttons": [
            {"title": str(b.get("title", "")), "payload": str(b.get("payload", ""))}
            for b in buttons
            if isinstance(b, dict) and b.get("title") and b.get("payload")
        ],
    })
    return answer


@rasa_bp.post("/api/askivy/chat-rasa")
def askivy_chat_rasa():
    payload = request.get_json(silent=True) or {}
    employee_id = payload.get("employeeId")
    question = str(payload.get("message", "")).strip()

    if not employee_id or not question:
        return jsonify({"error": "employeeId and message are required."}), 400

    employee = Employee.query.get_or_404(employee_id)

    try:
        response = requests.post(
            f"{RASA_URL}/webhooks/rest/webhook",
            json={"sender": employee.id, "message": question},
            timeout=RASA_TIMEOUT,
        )
        response.raise_for_status()
        messages = response.json()
    except requests.RequestException:
        # 200 on purpose: the widget renders `text` and would otherwise show a
        # bare "Request failed: 502" with no guidance.
        return jsonify(_blank_answer(UNREACHABLE_TEXT))

    if not isinstance(messages, list):
        return jsonify(_blank_answer(FALLBACK_TEXT))

    answer = _merge_rasa_messages(messages)

    # Log what the employee saw themselves send, not the wire payload. A clicked button
    # sends "/SetSlots(confirm_flag_hr=true)" as the message; the support conversation log
    # should read "Yes, raise it with HR". Falls back to the raw message for typed input,
    # where the two are the same thing.
    chat = ChatMessage(
        employee_id=employee.id,
        question=str(payload.get("displayText") or question),
        response=answer["text"],
        policy_used=answer.get("source"),
    )
    db.session.add(chat)
    db.session.commit()

    return jsonify(answer)


@rasa_bp.post("/api/askivy/rasa/reset")
def askivy_rasa_reset():
    """Wipe one employee's Rasa conversation state.

    Needed because sender_id == employeeId, so the tracker persists between
    demo runs — a half-finished apply_for_leave flow would otherwise resume
    mid-conversation the next time you open the widget.
    """
    payload = request.get_json(silent=True) or {}
    employee_id = payload.get("employeeId")
    if not employee_id:
        return jsonify({"error": "employeeId is required."}), 400

    try:
        response = requests.post(
            f"{RASA_URL}/conversations/{employee_id}/tracker/events",
            json=[{"event": "restart"}],
            timeout=RASA_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Could not reset Rasa conversation: {exc}"}), 502

    return jsonify({"message": f"Conversation reset for {employee_id}."})


@rasa_bp.get("/api/askivy/rasa/health")
def askivy_rasa_health():
    """Is the Rasa server up and does it have a trained model loaded?

    Saves a lot of guessing when the widget says "can't reach the reasoning
    service" — this tells you whether it's Rasa or the model that's missing.
    """
    try:
        response = requests.get(f"{RASA_URL}/status", timeout=5)
        response.raise_for_status()
        status = response.json()
    except requests.RequestException as exc:
        return jsonify({"status": "unreachable", "rasaUrl": RASA_URL, "detail": str(exc)}), 503

    return jsonify({
        "status": "ok" if status.get("model_id") else "no_model_loaded",
        "rasaUrl": RASA_URL,
        "modelFile": status.get("model_file"),
    })
