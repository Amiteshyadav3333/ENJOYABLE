import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'podcast-secret-key')

# Database configuration for Render PostgreSQL
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///podcast.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_creator = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Podcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_live = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database after models
try:
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                is_creator=True
            )
            db.session.add(admin)
            db.session.commit()
except Exception as e:
    print(f'Database init error: {e}')

@app.route('/')
def index():
    return send_from_directory('../frontend', 'simple.html')

@app.route('/test')
def test_page():
    return send_from_directory('../frontend', 'test.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_creator=True
        )
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'Registration successful', 'user_id': user.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'is_creator': user.is_creator
                }
            })
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/podcasts', methods=['GET'])
def get_podcasts():
    podcasts = Podcast.query.filter_by(is_live=True).all()
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'room_id': f'room_{p.id}'
    } for p in podcasts])

@app.route('/api/podcasts', methods=['POST'])
def create_podcast():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    podcast = Podcast(
        title=data.get('title'),
        description=data.get('description'),
        creator_id=session['user_id'],
        is_live=True
    )
    db.session.add(podcast)
    db.session.commit()
    
    return jsonify({
        'podcast_id': podcast.id,
        'room_id': f'room_{podcast.id}',
        'message': 'Podcast created successfully'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/test', methods=['GET', 'POST'])
def test():
    return jsonify({
        'method': request.method,
        'data': request.get_json() if request.method == 'POST' else None,
        'status': 'API working'
    })

@app.route('/api/init-db')
def init_db():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def list_users():
    try:
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'is_creator': u.is_creator
        } for u in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)