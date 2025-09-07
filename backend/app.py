from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'simple-key'
CORS(app)

# Simple in-memory storage
users = {'admin': 'admin123', 'test': 'test123'}
podcasts = []

@app.route('/')
def index():
    return send_from_directory('../frontend', 'simple.html')

@app.route('/quick')
def quick_test():
    return send_from_directory('../frontend', 'quick_test.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    print(f'Login data received: {data}')
    
    username = data.get('username') if data else None
    password = data.get('password') if data else None
    
    print(f'Username: {username}, Password: {password}')
    print(f'Available users: {list(users.keys())}')
    
    if username in users and users[username] == password:
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': 1,
                'username': username,
                'is_creator': True
            }
        })
    return jsonify({'error': f'Invalid credentials. Got username: {username}, password: {password}'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username in users:
        return jsonify({'error': 'Username already exists'}), 400
    
    users[username] = password
    return jsonify({'message': 'Registration successful', 'user_id': len(users)})

@app.route('/api/podcasts', methods=['GET'])
def get_podcasts():
    return jsonify(podcasts)

@app.route('/api/podcasts', methods=['POST'])
def create_podcast():
    data = request.get_json()
    podcast = {
        'id': len(podcasts) + 1,
        'title': data.get('title'),
        'description': data.get('description'),
        'room_id': f'room_{len(podcasts) + 1}'
    }
    podcasts.append(podcast)
    return jsonify(podcast)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)