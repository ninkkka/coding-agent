# app.py
import os
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load env before importing/using other modules that depend on them
load_dotenv()

# Import handler after env loaded
from handler import handle_build_request

app = Flask(__name__)

REQUIRED_FIELDS = ("email", "secret", "task", "round", "nonce", "brief", "evaluation_url")

@app.route('/api-endpoint', methods=['GET', 'POST'])
def api_endpoint():
    # --- GET request (status check) ---
    if request.method == 'GET':
        return jsonify({
            "status": "ok",
            "message": "LLM Code Deployment API is live and ready.",
            "endpoint": "/api-endpoint",
            "usage": "Send a POST request with JSON payload containing: email, secret, task, round, nonce, brief, evaluation_url"
        }), 200


    # --- POST request (main task) ---
    # quick content-type check
    if not request.is_json:
        return jsonify({"error": "Expected application/json payload"}), 400

    data = request.get_json(silent=True) or {}

    # validate required fields
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    # Secret Verification (CRITICAL CHECK)
    expected = os.getenv('MY_SECRET')
    if not expected:
        # defensive: don't reveal secret value
        app.logger.warning("MY_SECRET not set in environment.")
        return jsonify({"error": "Server misconfiguration"}), 500

    if data.get('secret') != expected:
        app.logger.warning("Invalid secret attempt for task: %s", data.get('task'))
        return jsonify({"error": "Invalid secret."}), 403

    # Start background processing (daemon so it won't block shutdown)
    try:
        thread = threading.Thread(target=handle_build_request, args=(data,))
        thread.daemon = True
        thread.start()

        app.logger.info("Task processing started in background for: %s", data.get('task'))
        return jsonify({"message": "Request received and is being processed."}), 200
    except Exception as e:
        app.logger.exception("Error starting background thread")
        return jsonify({"error": "Failed to start processing."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 7860)))
