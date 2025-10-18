# app.py
import os
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv() 

# Now import your handler, which needs those variables
from handler import handle_build_request



app = Flask(__name__)

@app.route('/api-endpoint', methods=['GET', 'POST'])
def api_endpoint():
    # --- GET request (status check) ---
    if request.method == 'GET':
        return jsonify({
            "status": "ok",
            "message": "LLM Code Deployment API is live and ready.",
            "usage": "Send a POST request with JSON payload (email, secret, task, round, nonce, brief, evaluation_url)."
        }), 200

    # --- POST request (main task) ---
    print("Received a new task request.")
    data = request.get_json()

    # 1. Secret Verification (CRITICAL CHECK)
    if not data or data.get('secret') != os.getenv('MY_SECRET'):
        print("Error: Invalid or missing secret.")
        return jsonify({"error": "Invalid secret."}), 403

    # 2. Respond 200 OK Immediately (process async)
    try:
        thread = threading.Thread(target=handle_build_request, args=(data,))
        thread.start()
        print(f"Task processing started in background for: {data.get('task')}")
        return jsonify({"message": "Request received and is being processed."}), 200
    except Exception as e:
        print(f"Error starting background thread: {e}")
        return jsonify({"error": "Failed to start processing."}), 500

# This part lets you run the server locally for testing
if __name__ == '__main__':
    # Hugging Face Spaces uses port 7860 by default
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 7860)))
