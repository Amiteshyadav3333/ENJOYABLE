import eventlet
eventlet.monkey_patch()

import os
import re
import uuid
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from twilio.rest import Client

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your-secret-key'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'database', 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
CORS(app)

# Twilio Config
TWILIO_ACCOUNT_SID = 'your_account_sid'
TWILIO_AUTH_TOKEN = 'your_auth_token'
TWILIO_PHONE_NUMBER = '+1XXXXXXXXXX'
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# SQLAlchemy Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    mobile = db.Column(db.String(15), unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    sid = db.Column(db.String(100))
    room = db.Column(db.String(50))

# ------------------- OTP Handling ---------------------
@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    mobile = data.get('mobile')

    if not mobile or not re.match(r'^\+91[6-9]\d{9}$', mobile):
        return jsonify({'success': False, 'message': 'Invalid mobile number'}), 400

    otp = str(random.randint(1000, 9999))
    session['otp'] = otp
    session['otp_expiry'] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    try:
        twilio_client.messages.create(
            body=f"Your OTP for LiveCast Signup is: {otp}",
            from_=TWILIO_PHONE_NUMBER,
            to=mobile
        )
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    entered_otp = data.get('otp')

    if 'otp' not in session or 'otp_expiry' not in session:
        return jsonify({'success': False, 'message': 'OTP not sent'})

    expiry = datetime.fromisoformat(session['otp_expiry'])
    if datetime.utcnow() > expiry:
        return jsonify({'success': False, 'message': 'OTP expired'})

    if entered_otp == session['otp']:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Incorrect OTP'})

# ------------------- Signup ---------------------
def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[a-z]', password) and
        re.search(r'\d', password) and
        re.search(r'[!@#$%^&*]', password)
    )

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    mobile = data.get('mobile')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400

    if not is_strong_password(password):
        return jsonify({"message": "Password must be 8+ chars with uppercase, lowercase, number, and symbol."}), 400

    if not re.match(r'^\+91[6-9]\d{9}$', mobile or ''):
        return jsonify({"message": "Invalid mobile number"}), 400

    if db.session.query(User).filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 409

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        mobile=mobile,
        is_admin=is_admin
    )
    db.session.add(user)
    db.session.commit()

    # ✅ Auto-login
    session['username'] = username
    return jsonify({"message": "Signup successful"}), 200

# ------------------- Pages ---------------------
@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        session['username'] = username
        return redirect('/')
    return render_template('login.html')

@app.route('/signup', methods=['GET'])
def signup_page():
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ------------------- Socket.IO ---------------------
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
    if not room: return
    users = [{'sid': sid, 'username': info['username']} for sid, info in room['participants'].items()]
    emit('user_list', users, room=room_id)

# ------------------- Run Server ---------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            ))
            db.session.commit()
            print("✅ Created admin user: admin / admin123")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)