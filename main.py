import os
import uuid
import asyncio
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agent import root_agent

load_dotenv()

app = Flask(__name__)

session_service = InMemorySessionService()
APP_NAME = "bizpulse"

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service
)

# Create a single persistent event loop
loop = asyncio.new_event_loop()


async def run_agent(user_id, session_id, message):
    # Create session
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )

    content = Content(parts=[Part(text=message)])
    response_text = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    response_text = part.text

    return response_text


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "BizPulse AI is running"}), 200


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "message field required"}), 400

        user_message = data["message"]
        session_id = data.get("session_id", str(uuid.uuid4()))
        user_id = data.get("user_id", "default_user")

        response_text = loop.run_until_complete(
            run_agent(user_id, session_id, user_message)
        )

        return jsonify({
            "response": response_text,
            "session_id": session_id,
            "user_id": user_id
        }), 200

    except Exception as e:
        logging.error(f"[BizPulse] Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)