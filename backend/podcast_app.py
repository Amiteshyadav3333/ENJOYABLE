import os
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Podcast, LiveSession, ChatMessage

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'podcast-secret-key')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///podcast.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# In-memory storage for active rooms
active_rooms = {}

# ============ Authentication Routes ============
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    is_creator = data.get('is_creator', False)
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_creator=is_creator
    )
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    return jsonify({'message': 'Registration successful', 'user_id': user.id})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'is_creator': user.is_creator,
                'is_admin': user.is_admin
            }
        })
    return jsonify({'error': 'Invalid credentials'}), 401

# ============ Podcast Management ============
@app.route('/api/podcasts', methods=['GET'])
def get_podcasts():
    podcasts = Podcast.query.filter_by(is_live=True).all()
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'room_id': p.room_id,
        'language': p.language
    } for p in podcasts])

@app.route('/api/podcasts', methods=['POST'])
def create_podcast():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    room_id = str(uuid.uuid4())
    
    podcast = Podcast(
        title=data.get('title'),
        description=data.get('description'),
        creator_id=session['user_id'],
        room_id=room_id,
        language=data.get('language', 'en')
    )
    db.session.add(podcast)
    db.session.commit()
    
    return jsonify({
        'podcast_id': podcast.id,
        'room_id': room_id,
        'message': 'Podcast created successfully'
    })

@app.route('/api/podcasts/<int:podcast_id>/start', methods=['POST'])
def start_live_session(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    if podcast.creator_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    podcast.is_live = True
    live_session = LiveSession(podcast_id=podcast_id, room_id=podcast.room_id)
    db.session.add(live_session)
    db.session.commit()
    
    active_rooms[podcast.room_id] = {
        'podcast_id': podcast_id,
        'host_id': podcast.creator_id,
        'participants': {},
        'chat_enabled': True,
        'qa_mode': False
    }
    
    return jsonify({'message': 'Live session started', 'room_id': podcast.room_id})

# ============ WebSocket Events ============
@socketio.on('join_podcast')
def handle_join_podcast(data):
    room_id = data.get('room_id')
    username = data.get('username', 'Anonymous')
    
    if room_id not in active_rooms:
        emit('error', {'message': 'Podcast not found'})
        return
    
    join_room(room_id)
    active_rooms[room_id]['participants'][request.sid] = {
        'username': username,
        'user_id': session.get('user_id'),
        'has_mic': False
    }
    
    # Update participant count
    live_session = LiveSession.query.filter_by(room_id=room_id, ended_at=None).first()
    if live_session:
        live_session.participants_count = len(active_rooms[room_id]['participants'])
        db.session.commit()
    
    emit('joined_podcast', {
        'room_id': room_id,
        'participant_count': len(active_rooms[room_id]['participants'])
    })
    
    emit('user_joined', {
        'username': username,
        'participant_count': len(active_rooms[room_id]['participants'])
    }, room=room_id)

@socketio.on('send_chat')
def handle_chat_message(data):
    room_id = data.get('room_id')
    message = data.get('message')
    
    if room_id not in active_rooms:
        return
    
    participant = active_rooms[room_id]['participants'].get(request.sid)
    if not participant:
        return
    
    # Save to database
    chat_msg = ChatMessage(
        room_id=room_id,
        user_id=participant.get('user_id'),
        message=message
    )
    db.session.add(chat_msg)
    db.session.commit()
    
    emit('chat_message', {
        'username': participant['username'],
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }, room=room_id)

@socketio.on('send_reaction')
def handle_reaction(data):
    room_id = data.get('room_id')
    reaction = data.get('reaction')
    
    if room_id not in active_rooms:
        return
    
    participant = active_rooms[room_id]['participants'].get(request.sid)
    if not participant:
        return
    
    emit('reaction', {
        'username': participant['username'],
        'reaction': reaction
    }, room=room_id)

@socketio.on('request_mic')
def handle_mic_request(data):
    room_id = data.get('room_id')
    
    if room_id not in active_rooms:
        return
    
    participant = active_rooms[room_id]['participants'].get(request.sid)
    if not participant:
        return
    
    # Notify host about mic request
    host_id = active_rooms[room_id]['host_id']
    emit('mic_request', {
        'username': participant['username'],
        'user_sid': request.sid
    }, room=f"user_{host_id}")

@socketio.on('grant_mic')
def handle_grant_mic(data):
    room_id = data.get('room_id')
    target_sid = data.get('target_sid')
    
    if room_id not in active_rooms:
        return
    
    # Check if user is host
    if session.get('user_id') != active_rooms[room_id]['host_id']:
        return
    
    if target_sid in active_rooms[room_id]['participants']:
        active_rooms[room_id]['participants'][target_sid]['has_mic'] = True
        emit('mic_granted', {}, room=target_sid)
        emit('user_got_mic', {
            'username': active_rooms[room_id]['participants'][target_sid]['username']
        }, room=room_id)

@socketio.on('webrtc_signal')
def handle_webrtc_signal(data):
    target_sid = data.get('target_sid')
    signal_data = data.get('signal')
    
    emit('webrtc_signal', {
        'from_sid': request.sid,
        'signal': signal_data
    }, room=target_sid)

@socketio.on('disconnect')
def handle_disconnect():
    for room_id, room_data in active_rooms.items():
        if request.sid in room_data['participants']:
            participant = room_data['participants'][request.sid]
            del room_data['participants'][request.sid]
            
            # Update participant count
            live_session = LiveSession.query.filter_by(room_id=room_id, ended_at=None).first()
            if live_session:
                live_session.participants_count = len(room_data['participants'])
                db.session.commit()
            
            emit('user_left', {
                'username': participant['username'],
                'participant_count': len(room_data['participants'])
            }, room=room_id)
            break

# ============ Health Check ============
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/')
def index():
    return app.send_static_file('../frontend/index.html')

@app.route('/api')
def api_info():
    return jsonify({
        'message': 'Live Interactive Podcast Platform API',
        'version': '1.0.0',
        'features': [
            'Real-time audio streaming',
            'Interactive chat',
            'Live reactions',
            'Q&A sessions',
            'Multi-language support'
        ]
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@podcast.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True,
                is_creator=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: admin / admin123")
    
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)