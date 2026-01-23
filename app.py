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

    # Check for Vercel Environment Variable
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
            
            if 'timestamp' in msg_data and msg_data['timestamp']:
                msg_data['timestamp'] = int(msg_data['timestamp'].timestamp() * 1000)
                
            all_messages.append(msg_data)
            
        return jsonify(all_messages), 200
    except Exception as e:
        print(f"Error: {e}") 
        return jsonify({"error": str(e)}), 500


# 2. Send Message (POST)
@app.route('/messages', methods=['POST'])
def send_message():
    try:
        data = request.json
        
        # Validate required fields
        if not data or 'conversationId' not in data or 'senderId' not in data or 'text' not in data:
            return jsonify({"error": "Missing required fields"}), 400

        # Construct the Message Object
        new_message = {
            'conversationId': data['conversationId'],
            'senderId': data['senderId'],
            'text': data['text'],
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 1, # Sent
            
            # Capture Reply Fields (Optional)
            'replyToId': data.get('replyToId'),
            'replyToName': data.get('replyToName'),
            'replyToText': data.get('replyToText')
        }

        # Save to Firestore
        update_time, ref = db.collection('messages').add(new_message)

         # Update Conversation
        convo_ref = db.collection('conversations').document(data['conversationId'])
        convo_ref.update({
            "lastMessage": data['text'],
            "lastUpdated": firestore.SERVER_TIMESTAMP
        })

        # Return the new ID
        return jsonify({"status": "sent", "id": ref.id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 3. Create Conversation (POST)
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
            "createdAt": firestore.SERVER_TIMESTAMP,
            "metadata": metadata
        }

        db.collection('conversations').document(conversation_id).set(new_chat, merge=True)
        return jsonify({"status": "success", "id": conversation_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 4. Get All Conversations (GET)
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
            
            if 'lastUpdated' in data and data['lastUpdated']:
                data['lastUpdated'] = int(data['lastUpdated'].timestamp() * 1000)
            
            if 'createdAt' in data and data['createdAt']:
                data['createdAt'] = int(data['createdAt'].timestamp() * 1000)
                
            results.append(data)
            
        return jsonify(results), 200
    except Exception as e:
        print(f"Error: {e}") # Print error to Vercel logs
        return jsonify({"error": str(e)}), 500


# 5. Update Conversation Title (PATCH)
@app.route('/conversations/<conversation_id>', methods=['PATCH'])
def update_conversation_title(conversation_id):
    try:
        data = request.json
        new_title = data.get('title')
        
        if not new_title:
             return jsonify({"error": "title is required"}), 400

        # Update specific field in Firestore
        db.collection('conversations').document(conversation_id).update({
            "metadata.title": new_title,
            "lastUpdated": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"status": "updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 6. Delete Conversation (DELETE)
@app.route('/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        # Delete the conversation document
        db.collection('conversations').document(conversation_id).delete()
        
        return jsonify({"status": "deleted"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 7. Delete Message (DELETE)
@app.route('/messages/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    try:
        # Delete the message document
        db.collection('messages').document(message_id).delete()

        return jsonify({"status": "deleted"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 8. Edit Message (PATCH)
@app.route('/messages/<message_id>', methods=['PATCH'])
def edit_message(message_id):
    try:
        data = request.json
        new_text = data.get('text')
        
        if not new_text:
             return jsonify({"error": "text is required"}), 400

        # Update the text field
        db.collection('messages').document(message_id).update({
            "text": new_text
        })
        
        return jsonify({"status": "updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Required for Vercel
if __name__ == '__main__':
    app.run(debug=True)