import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Database Config
# updated the path
db_uri = os.environ.get('DATABASE_URL', 'postgresql://postgres:AE10b$$e@34.173.159.63:5432/mac_theme_db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    profession = db.Column(db.String(100))
    bio = db.Column(db.String(255))
    avatar = db.Column(db.Text)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "profession": self.profession,
            "bio": self.bio,
            "avatar": self.avatar
        }

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    date = db.Column(db.Date, nullable=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "is_completed": self.is_completed,
            "date": self.date.isoformat()
        }

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    title = db.Column(db.String(255))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# --- Helper to get user ---
def get_user_from_request():
    # In a real app, use session/token. Here we rely on 'username' header or query param for simplicity
    username = request.headers.get('X-Username')
    if not username:
        return None
    return Profile.query.filter_by(name=username).first()

@app.route('/api/todos', methods=['GET'])
def get_todos():
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
    
    date_str = request.args.get('date')
    query = Todo.query.filter_by(user_id=user.id)
    
    if date_str:
        query = query.filter_by(date=date_str)
        
    todos = query.order_by(Todo.id).all()
    return jsonify([t.to_dict() for t in todos])

@app.route('/api/todos', methods=['POST'])
def add_todo():
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
        
    data = request.json
    if not data or not data.get('text') or not data.get('date'):
        return jsonify({"error": "Text and date required"}), 400
        
    new_todo = Todo(
        user_id=user.id,
        text=data['text'],
        date=data['date'],
        is_completed=False
    )
    
    db.session.add(new_todo)
    db.session.commit()
    
    return jsonify(new_todo.to_dict())

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
        
    todo = Todo.query.filter_by(id=todo_id, user_id=user.id).first()
    if not todo:
        return jsonify({"error": "Todo not found"}), 404
        
    data = request.json
    if 'is_completed' in data:
        todo.is_completed = data['is_completed']
    if 'text' in data:
        todo.text = data['text']
        
    db.session.commit()
    return jsonify(todo.to_dict())

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
        
    todo = Todo.query.filter_by(id=todo_id, user_id=user.id).first()
    if not todo:
        return jsonify({"error": "Todo not found"}), 404
        
    db.session.delete(todo)
    db.session.commit()
    return jsonify({"message": "Todo deleted"})

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    if not data or not data.get('name') or not data.get('password'):
        return jsonify({"error": "Name and password required"}), 400
    
    if Profile.query.filter_by(name=data['name']).first():
        return jsonify({"error": "User already exists"}), 400
    
    new_user = Profile(
        name=data['name'],
        profession=data.get('profession', ''),
        avatar=data.get('avatar', ''),
        bio=data.get('bio', '')  # Optional initial bio
    )
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "Signup successful", "user": new_user.to_dict()})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data or not data.get('name') or not data.get('password'):
        return jsonify({"error": "Name and password required"}), 400
        
    user = Profile.query.filter_by(name=data['name']).first()
    
    if user and user.check_password(data['password']):
        return jsonify({"message": "Login successful", "user": user.to_dict()})
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/profile', methods=['POST'])
def update_profile():
    # Simplistic: "Login" just gives you the right to edit if you know the name? 
    # For a real app we need tokens. 
    # For this task, we will just rely on the user sending the name (username) to identify which record to update.
    # We will assume client sends { "name": "...", "profession": "..." } and we update that user.
    # A bit insecure but fits the scope of "add login section" without full JWT implementation unless requested.
    
    data = request.json
    username = data.get('name')
    if not username:
        return jsonify({"error": "Username required to identify profile"}), 400
        
    user = Profile.query.filter_by(name=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Update fields
    if 'profession' in data: user.profession = data['profession']
    if 'bio' in data: user.bio = data['bio']
    if 'avatar' in data: user.avatar = data['avatar']
    
    db.session.commit()
    return jsonify({"message": "Profile updated", "user": user.to_dict()})

@app.route('/api/profile', methods=['GET'])
def get_profile():
    # Require ?name=...
    username = request.args.get('name')
    if not username:
        return jsonify({"error": "Name parameter required"}), 400
        
    user = Profile.query.filter_by(name=username).first()
    if not user:
         return jsonify({"error": "User not found"}), 404
         
    return jsonify(user.to_dict())

# --- Notes Endpoints ---
@app.route('/api/notes', methods=['GET'])
def get_notes():
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
    
    notes = Note.query.filter_by(user_id=user.id).order_by(Note.updated_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])

@app.route('/api/notes', methods=['POST'])
def create_note():
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
    
    data = request.json
    new_note = Note(
        user_id=user.id,
        title=data.get('title', ''),
        body=data.get('body', '')
    )
    
    db.session.add(new_note)
    db.session.commit()
    return jsonify(new_note.to_dict())

@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    user = get_user_from_request()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401
        
    note = Note.query.filter_by(id=note_id, user_id=user.id).first()
    if not note:
        return jsonify({"error": "Note not found"}), 404
        
    data = request.json
    if 'title' in data: note.title = data['title']
    if 'body' in data: note.body = data['body']
    
    db.session.commit()
    return jsonify(note.to_dict())

    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Note deleted"})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    if not data or not data.get('message') or not data.get('apiKey'):
        return jsonify({"error": "Message and API Key required"}), 400
    
    api_key = data['apiKey']
    user_message = data['message']
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": user_message}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
             return jsonify({"error": f"Gemini API Error: {response.text}"}), response.status_code
             
        ai_response = response.json()
        # Extract text from Gemini response structure
        try:
            text = ai_response['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"reply": text})
        except (KeyError, IndexError):
            return jsonify({"error": "Invalid response format from Gemini"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "text": self.text,
            "created_at": self.created_at.isoformat()
        }

# --- Chat Endpoints ---
@app.route('/api/users', methods=['GET'])
def get_users():
    current_user = get_user_from_request()
    # In a real app, you might want to require auth, but for "Add Chat" we just need a list.
    # We'll filter out the current user if authenticated.
    
    users = Profile.query.all()
    user_list = []
    
    for u in users:
        if current_user and u.id == current_user.id:
            continue
        user_list.append(u.to_dict())
        
    return jsonify(user_list)

@app.route('/api/messages', methods=['POST'])
def send_message():
    sender = get_user_from_request()
    if not sender:
        return jsonify({"error": "User not authenticated"}), 401
    
    data = request.json
    if not data or not data.get('receiver_id') or not data.get('text'):
        return jsonify({"error": "Receiver and text required"}), 400
    
    new_msg = Message(
        sender_id=sender.id,
        receiver_id=data['receiver_id'],
        text=data['text']
    )
    
    db.session.add(new_msg)
    db.session.commit()
    
    return jsonify(new_msg.to_dict())

@app.route('/api/messages/history', methods=['GET'])
def get_message_history():
    try:
        user = get_user_from_request()
        if not user:
            return jsonify({"error": "User not authenticated"}), 401
        
        partner_id = request.args.get('partner_id', type=int)
        if not partner_id:
            return jsonify({"error": "Partner ID required"}), 400
            
        # Fetch messages between user and partner (both directions)
        # (sender=me AND receiver=them) OR (sender=them AND receiver=me)
        from sqlalchemy import or_, and_
        
        messages = Message.query.filter(
            or_(
                and_(Message.sender_id == user.id, Message.receiver_id == partner_id),
                and_(Message.sender_id == partner_id, Message.receiver_id == user.id)
            )
        ).order_by(Message.created_at.asc()).all()
        
        return jsonify([m.to_dict() for m in messages])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ensure tables exist (Run on import for Gunicorn/Render)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
