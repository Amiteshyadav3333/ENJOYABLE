import eventlet
eventlet.monkey_patch()

import os
import sqlite3
import uuid
import traceback
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# -------------------------
# Configuration
# -------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'database', 'users.db')

app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------
# SQLAlchemy Model
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    mobile = db.Column(db.String(15), unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    sid = db.Column(db.String(100))
    room = db.Column(db.String(50))

# -------------------------
# Routes for frontend templates
# -------------------------
@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect('/login')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# -------------------------
# API Routes for JS fetch
# -------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({"message": "Login successful"}), 200
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        print("Login error:", str(e))
        traceback.print_exc()
        return jsonify({"message": "Internal Server Error"}), 500

@app.route('/signup', methods=['POST'])
def api_signup():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        mobile = data.get('mobile')
        is_admin = data.get('is_admin', False)

        if User.query.filter_by(username=username).first():
            return jsonify({"message": "Username already exists"}), 409

        password_hash = generate_password_hash(password)
        user = User(username=username, mobile=mobile, password_hash=password_hash, is_admin=is_admin)
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "Signup successful"}), 201
    except Exception as e:
        print("Signup error:", str(e))
        traceback.print_exc()
        return jsonify({"message": "Internal Server Error"}), 500

# -------------------------
# Socket.IO Logic
# -------------------------
rooms = {}

@socketio.on('connect')
def on_connect():
    print('Client connected:', request.sid)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print('Client disconnected:', sid)
    for room_id, room in list(rooms.items()):
        if sid in room['participants']:
            username = room['participants'][sid]['username']
            leave_room(room_id)
            del room['participants'][sid]
            emit('user_left', {'sid': sid, 'username': username}, room=room_id)
            if sid == room['admin']:
                if room['participants']:
                    new_admin = next(iter(room['participants']))
                    room['admin'] = new_admin
                    emit('admin_changed', {'sid': new_admin}, room=room_id)
                else:
                    del rooms[room_id]
            break

@socketio.on('create_room')
def create_room(data):
    username = data.get('username', 'Anonymous')
    room_id = str(uuid.uuid4())
    rooms[room_id] = {
        'name': data.get('room_name', 'Room'),
        'admin': request.sid,
        'participants': {request.sid: {'username': username}}
    }
    join_room(room_id)
    emit('room_created', {'room_id': room_id, 'admin': True})
    _update_user_list(room_id)

@socketio.on('join_room')
def join_room_evt(data):
    room_id = data['room_id']
    username = data.get('username', 'Anonymous')
    room = rooms.get(room_id)
    if not room:
        emit('error', {'msg': 'Room not found'})
        return
    room['participants'][request.sid] = {'username': username}
    join_room(room_id)
    emit('user_joined', {'sid': request.sid, 'username': username}, room=room_id)
    _update_user_list(room_id)
    emit('joined_success', {'room_id': room_id, 'admin': request.sid == room['admin']})

@socketio.on('chat_message')
def chat_message(data):
    emit('chat_message', {'sid': request.sid, 'text': data['text']}, room=data['room_id'])

@socketio.on('reaction')
def reaction(data):
    emit('reaction', {'sid': request.sid, 'emoji': data['emoji']}, room=data['room_id'])

@socketio.on('signal')
def signal(data):
    emit('signal', {'sid': request.sid, 'signal': data['signal']}, room=data['target'])

@socketio.on('admin_action')
def admin_action(data):
    room_id = data['room_id']
    action = data['action']
    target = data['target']
    room = rooms.get(room_id)
    if not room or request.sid != room['admin']:
        emit('error', {'msg': 'Not authorized'})
        return
    if action == 'kick':
        emit('kicked', {}, room=target)
        leave_room(room_id, sid=target)
        room['participants'].pop(target, None)
        _update_user_list(room_id)
    else:
        emit('admin_action', {'action': action}, room=target)

def _update_user_list(room_id):
    room = rooms.get(room_id)
    if not room:
        return
    users = [{'sid': sid, 'username': info['username']} for sid, info in room['participants'].items()]
    emit('user_list', users, room=room_id)

# -------------------------
# Server Start
# -------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)