import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables (for local testing)
load_dotenv()

app = Flask(__name__)

# --- FIREBASE SETUP ---
# We check if we are on Vercel (Cloud) or Local (Computer)
def initialize_firebase():
    # If app is already initialized, do nothing
    if firebase_admin._apps:
        return firestore.client()

    # Check for Vercel Environment Variable (We will set this later in Phase 1.5)
    firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')

    if firebase_creds_json:
        # We are on Vercel: Load from String
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
    else:
        # We are Local: Load from File
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
        else:
            raise Exception("No Firebase Key found! Check serviceAccountKey.json or env vars.")

    firebase_admin.initialize_app(cred)
    return firestore.client()

# Initialize DB
db = initialize_firebase()

# --- ROUTES ---

@app.route('/')
def home():
    return "Chat API is running! 🚀"

# 1. Get Messages (GET)
# @app.route('/messages', methods=['GET'])
# def get_messages():
#     try:
#         # Get 'messages' collection, order by time
#         messages_ref = db.collection('messages').order_by('timestamp', direction=firestore.Query.ASCENDING)
#         docs = messages_ref.stream()
        
#         all_messages = []
#         for doc in docs:
#             msg_data = doc.to_dict()
#             # Add the ID so we can identify messages if needed
#             msg_data['id'] = doc.id 
#             all_messages.append(msg_data)
            
#         return jsonify(all_messages), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# 1. GET Messages with PAGINATION and CONVERSATION ID
@app.route('/messages', methods=['GET'])
def get_messages():
    try:
        # Get query parameters
        conversation_id = request.args.get('conversationId')
        limit = int(request.args.get('limit', 20)) # Default to 20 messages
        last_timestamp = request.args.get('lastTimestamp') # For pagination (load older messages)

        if not conversation_id:
            return jsonify({"error": "conversationId is required"}), 400

        # Start Query: Filter by Conversation, Order by Newest First
        messages_ref = db.collection('messages') \
            .where('conversationId', '==', conversation_id) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING) \
            .limit(limit)

        # Pagination Logic: If we have a timestamp, start AFTER it (fetching older messages)
        if last_timestamp:
            messages_ref = messages_ref.start_after({'timestamp': int(last_timestamp)})

        docs = messages_ref.stream()
        
        all_messages = []
        for doc in docs:
            msg_data = doc.to_dict()
            msg_data['id'] = doc.id
            all_messages.append(msg_data)
            
        # We return NEWEST first. The Android App will reverse this to show standard chat (Old -> New).
        return jsonify(all_messages), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Send Message (POST)
# @app.route('/messages', methods=['POST'])
# def send_message():
#     try:
#         data = request.json
#         # Expected JSON: {"sender": "Name", "content": "Hello", "timestamp": 12345}
        
#         if not data or 'content' not in data:
#             return jsonify({"error": "Invalid data"}), 400

#         # Add to Firestore (Let Firestore generate the ID)
#         db.collection('messages').add(data)
        
#         return jsonify({"status": "success", "message": "Message saved"}), 201
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# 2. Update Send Message to include conversationId
@app.route('/messages', methods=['POST'])
def send_message():
    try:
        data = request.json
        # Expected: sender, content, timestamp, conversationId
        if 'conversationId' not in data:
            return jsonify({"error": "conversationId is required"}), 400

        db.collection('messages').add(data)
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Required for Vercel
if __name__ == '__main__':
    app.run(debug=True)