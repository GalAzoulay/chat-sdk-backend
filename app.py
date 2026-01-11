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
# 2. Update Send Message to include conversationId
# @app.route('/messages', methods=['POST'])
# def send_message():
#     try:
#         data = request.json
#         # Expected: sender, content, timestamp, conversationId
#         if 'conversationId' not in data:
#             return jsonify({"error": "conversationId is required"}), 400

#         db.collection('messages').add(data)
#         return jsonify({"status": "success"}), 201
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
    
# Update 'send_message' to also update the Conversation's 'lastMessage'
@app.route('/messages', methods=['POST'])
def send_message():
    try:
        data = request.json
        # Expected: conversationId, senderId, text
        
        # 1. Save Message
        data['timestamp'] = firestore.SERVER_TIMESTAMP
        db.collection('messages').add(data)
        
        # 2. Update Conversation (Simulating TripWise 'updateConversation' logic)
        convo_ref = db.collection('conversations').document(data['conversationId'])
        convo_ref.update({
            "lastMessage": data['text'],
            "lastUpdated": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"status": "sent"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# 3. Create a Conversation (Chat Room)
# @app.route('/conversations', methods=['POST'])
# def create_conversation():
#     try:
#         data = request.json
#         # Expected: {"conversationId": "room_paris", "title": "Trip to Paris"}
#         if 'conversationId' not in data or 'title' not in data:
#             return jsonify({"error": "conversationId and title are required"}), 400
        
#         # Save to 'conversations' collection
#         db.collection('conversations').document(data['conversationId']).set(data)
        
#         return jsonify({"status": "created"}), 201
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# @app.route('/conversations', methods=['POST'])
# def create_conversation():
#     try:
#         data = request.json
#         # TripWise needs: participants (list), lastMessage (string), lastUpdated (timestamp)
        
#         # 1. Validate
#         if 'participants' not in data:
#             return jsonify({"error": "participants list is required"}), 400

#         # 2. Generate Conversation ID (if not provided)
#         # TripWise Logic: Sort user IDs to make a unique room ID (userA_userB)
#         participants = sorted(data['participants'])
#         conversation_id = data.get('conversationId', f"{participants[0]}_{participants[1]}")
        
#         # 3. Prepare Data
#         new_chat = {
#             "id": conversation_id,
#             "participants": participants,
#             "lastMessage": data.get("lastMessage", ""),
#             "lastUpdated": firestore.SERVER_TIMESTAMP,
#             # We store metadata (names/pics) here to avoid extra queries later
#             "metadata": data.get("metadata", {}) 
#         }

#         # 4. Save to 'conversations' collection
#         db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        
#         return jsonify({"status": "success", "conversationId": conversation_id}), 201

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# 3. CREATE Conversation (THE FIX IS HERE)
@app.route('/conversations', methods=['POST'])
def create_conversation():
    try:
        data = request.json
        
        # --- FIX 1: Ensure we use the ID provided by the App ---
        conversation_id = data.get('id')
        if not conversation_id:
            return jsonify({"error": "id is required"}), 400

        # --- FIX 2: Ensure metadata exists for the title ---
        metadata = data.get('metadata', {})
        # Foolproof: If the app sent 'title' outside metadata, move it inside.
        if 'title' in data and 'title' not in metadata:
            metadata['title'] = data['title']

        new_chat = {
            "id": conversation_id,
            # Use .get() to avoid errors if participants are missing
            "participants": data.get('participants', []), 
            "lastMessage": data.get("lastMessage", "New Chat"),
            "lastUpdated": firestore.SERVER_TIMESTAMP,
            "metadata": metadata # Title is safely inside here now
        }

        # Crucial: Use .document(id).set() to use YOUR id, not a random one.
        db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        
        return jsonify({"status": "success", "id": conversation_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Get All Conversations
# @app.route('/conversations', methods=['GET'])
# def get_conversations():
#     try:
#         docs = db.collection('conversations').stream()
#         results = []
#         for doc in docs:
#             results.append(doc.to_dict())
#         return jsonify(results), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# # 4. Get Conversations (Smart Filter)
# @app.route('/conversations', methods=['GET'])
# def get_conversations():
#     try:
#         user_id = request.args.get('userId')
        
#         if user_id:
#             # SMART MODE: Only get chats where THIS user is a participant
#             # Note: This requires 'participants' to be an array in Firestore
#             docs = db.collection('conversations') \
#                 .where('participants', 'array_contains', user_id) \
#                 .order_by('lastUpdated', direction=firestore.Query.DESCENDING) \
#                 .stream()
#         else:
#             # DEBUG MODE: Get everything (if no user specified)
#             docs = db.collection('conversations').stream()

#         results = []
#         for doc in docs:
#             data = doc.to_dict()
#             data['id'] = doc.id # Ensure ID is included
#             results.append(data)
            
#         return jsonify(results), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# 4. GET Conversations (With Timestamp Fix)
@app.route('/conversations', methods=['GET'])
def get_conversations():
    try:
        user_id = request.args.get('userId')
        
        if user_id:
            # Get chats for specific user
            docs = db.collection('conversations') \
                .where('participants', 'array_contains', user_id) \
                .order_by('lastUpdated', direction=firestore.Query.DESCENDING) \
                .stream()
        else:
            # Fallback
            docs = db.collection('conversations').stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # --- THE FIX: Convert Timestamp to Milliseconds ---
            if 'lastUpdated' in data and data['lastUpdated']:
                # Convert to milliseconds for Android
                data['lastUpdated'] = int(data['lastUpdated'].timestamp() * 1000)
                
            results.append(data)
            
        return jsonify(results), 200
    except Exception as e:
        print(f"Error: {e}") # Print error to Vercel logs
        return jsonify({"error": str(e)}), 500

# Required for Vercel
if __name__ == '__main__':
    app.run(debug=True)