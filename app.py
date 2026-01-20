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


# 1. GET Messages with PAGINATION and CONVERSATION ID



# 1. GET Messages (With Timestamp Fix)
@app.route('/messages', methods=['GET'])
def get_messages():
    try:
        conversation_id = request.args.get('conversationId')
        limit = int(request.args.get('limit', 20))
        last_timestamp = request.args.get('lastTimestamp')

        if not conversation_id:
            return jsonify({"error": "conversationId is required"}), 400

        messages_ref = db.collection('messages') \
            .where('conversationId', '==', conversation_id) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING) \
            .limit(limit)

        if last_timestamp:
            messages_ref = messages_ref.start_after({'timestamp': int(last_timestamp)})

        docs = messages_ref.stream()
        all_messages = []
        for doc in docs:
            msg_data = doc.to_dict()
            msg_data['id'] = doc.id
            
            # --- THE FIX: Convert Timestamp to Milliseconds ---
            if 'timestamp' in msg_data and msg_data['timestamp']:
                msg_data['timestamp'] = int(msg_data['timestamp'].timestamp() * 1000)
                
            all_messages.append(msg_data)
            
        return jsonify(all_messages), 200
    except Exception as e:
        print(f"Error: {e}") 
        return jsonify({"error": str(e)}), 500

# 2. Send Message (POST)
# 2. Update Send Message to include conversationId
# 2. Update 'send_message' to also update the Conversation's 'lastMessage'
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
    
# new for pictures 20.1.26
# 2. SEND Message
# @app.route('/messages', methods=['POST'])
# def send_message():
#     try:
#         data = request.json
        
#         # 1. Save Message
#         data['timestamp'] = firestore.SERVER_TIMESTAMP
#         db.collection('messages').add(data)
        
#         # 2. Determine Preview Text
#         display_message = data.get('text', '')
#         if data.get('type') == 'image':
#             display_message = "📷 Image" # Show this in the list instead of Base64 garbage

#         # 3. Update Conversation
#         convo_ref = db.collection('conversations').document(data['conversationId'])
#         convo_ref.update({
#             "lastMessage": display_message,
#             "lastUpdated": firestore.SERVER_TIMESTAMP
#         })
        
#         return jsonify({"status": "sent"}), 201
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# 3. Create a Conversation (Chat Room)
# 3. CREATE Conversation (THE FIX IS HERE)
# @app.route('/conversations', methods=['POST'])
# def create_conversation():
#     try:
#         data = request.json
        
#         # --- FIX 1: Ensure we use the ID provided by the App ---
#         conversation_id = data.get('id')
#         if not conversation_id:
#             return jsonify({"error": "id is required"}), 400

#         # --- FIX 2: Ensure metadata exists for the title ---
#         metadata = data.get('metadata', {})
#         # Foolproof: If the app sent 'title' outside metadata, move it inside.
#         if 'title' in data and 'title' not in metadata:
#             metadata['title'] = data['title']

#         new_chat = {
#             "id": conversation_id,
#             # Use .get() to avoid errors if participants are missing
#             "participants": data.get('participants', []), 
#             "lastMessage": data.get("lastMessage", "New Chat"),
#             "lastUpdated": firestore.SERVER_TIMESTAMP,
#             "metadata": metadata # Title is safely inside here now
#         }

#         # Crucial: Use .document(id).set() to use YOUR id, not a random one.
#         db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        
#         return jsonify({"status": "success", "id": conversation_id}), 201

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# 3. CREATE Conversation (updated for conversation information (created at) 20.1.26)
@app.route('/conversations', methods=['POST'])
def create_conversation():
    try:
        data = request.json
        conversation_id = data.get('id')
        if not conversation_id:
            return jsonify({"error": "id is required"}), 400

        metadata = data.get('metadata', {})
        if 'title' in data and 'title' not in metadata:
            metadata['title'] = data['title']

        new_chat = {
            "id": conversation_id,
            "participants": data.get('participants', []), 
            "lastMessage": data.get("lastMessage", "New Chat"),
            "lastUpdated": firestore.SERVER_TIMESTAMP,
            "createdAt": firestore.SERVER_TIMESTAMP,  # <--- NEW FIELD
            "metadata": metadata
        }

        db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        return jsonify({"status": "success", "id": conversation_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# new for pictures 20.1.26
# 3. CREATE Conversation
# @app.route('/conversations', methods=['POST'])
# def create_conversation():
#     try:
#         data = request.json

#         conversation_id = data.get('id')
#         if not conversation_id:
#             return jsonify({"error": "id is required"}), 400

#         metadata = data.get('metadata', {})
#         # Foolproof: If the app sent 'title' outside metadata, move it inside.
#         if 'title' in data and 'title' not in metadata:
#             metadata['title'] = data['title']

#         # NEW: Accept photoBase64
#         if 'photoBase64' in data and 'photoBase64' not in metadata:
#             metadata['photoBase64'] = data['photoBase64']

#         new_chat = {
#             "id": conversation_id,
#             "participants": data.get('participants', []), 
#             "lastMessage": data.get("lastMessage", "New Chat"),
#             "lastUpdated": firestore.SERVER_TIMESTAMP,
#             "metadata": metadata
#         }

#         db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        
#         return jsonify({"status": "success", "id": conversation_id}), 201

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500



# 4. Get All Conversations
# 4. Get Conversations (Smart Filter)
# 4. GET Conversations (With Timestamp Fix)
# @app.route('/conversations', methods=['GET'])
# def get_conversations():
#     try:
#         user_id = request.args.get('userId')
        
#         if user_id:
#             # Get chats for specific user
#             docs = db.collection('conversations') \
#                 .where('participants', 'array_contains', user_id) \
#                 .order_by('lastUpdated', direction=firestore.Query.DESCENDING) \
#                 .stream()
#         else:
#             # Fallback
#             docs = db.collection('conversations').stream()

#         results = []
#         for doc in docs:
#             data = doc.to_dict()
#             data['id'] = doc.id
            
#             # --- THE FIX: Convert Timestamp to Milliseconds ---
#             if 'lastUpdated' in data and data['lastUpdated']:
#                 # Convert to milliseconds for Android
#                 data['lastUpdated'] = int(data['lastUpdated'].timestamp() * 1000)
                
#             results.append(data)
            
#         return jsonify(results), 200
#     except Exception as e:
#         print(f"Error: {e}") # Print error to Vercel logs
#         return jsonify({"error": str(e)}), 500

# 4. GET Conversations (updated for conversation information (created at) 20.1.26)
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
            
            # Convert Timestamps to Milliseconds
            if 'lastUpdated' in data and data['lastUpdated']:
                data['lastUpdated'] = int(data['lastUpdated'].timestamp() * 1000)
            
            # <--- NEW: Handle createdAt conversion
            if 'createdAt' in data and data['createdAt']:
                data['createdAt'] = int(data['createdAt'].timestamp() * 1000)
                
            results.append(data)
            
        return jsonify(results), 200
    except Exception as e:
        print(f"Error: {e}") # Print error to Vercel logs
        return jsonify({"error": str(e)}), 500

# new for pictures 20.1.26
# 7. UPDATE Conversation (PATCH)
# @app.route('/conversations/<conversation_id>', methods=['PATCH'])
# def update_conversation(conversation_id):
#     try:
#         data = request.json
#         # We only update what is sent (Title or Photo)
#         updates = {}
        
#         # 1. Handle Title Update
#         if 'title' in data:
#             # We store title in metadata.title
#             updates['metadata.title'] = data['title']

#         # 2. Handle Photo Update
#         if 'photoBase64' in data:
#             # Send null or empty string to delete the photo
#             photo = data['photoBase64']
#             if not photo:
#                 updates['metadata.photoBase64'] = firestore.DELETE_FIELD
#             else:
#                 updates['metadata.photoBase64'] = photo

#         if not updates:
#             return jsonify({"status": "no changes"}), 200

#         # 3. Apply Updates
#         # Update 'lastUpdated' so it bumps to the top of the list
#         updates['lastUpdated'] = firestore.SERVER_TIMESTAMP
        
#         db.collection('conversations').document(conversation_id).update(updates)
        
#         return jsonify({"status": "updated"}), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# Required for Vercel
if __name__ == '__main__':
    app.run(debug=True)