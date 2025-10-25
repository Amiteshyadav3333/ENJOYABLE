import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'simple-key'
CORS(app)

# Storage
users = {'admin': 'admin123', 'creator1': 'pass123'}
videos = []

@app.route('/')
def index():
    return send_from_directory('../frontend', 'video_platform.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if username in users and users[username] == password:
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': username,
                    'username': username,
                    'is_creator': True
                }
            })
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username in users:
        return jsonify({'error': 'Username already exists'}), 400
    
    users[username] = password
    return jsonify({'message': 'Registration successful', 'user_id': username})

@app.route('/api/videos', methods=['GET'])
def get_videos():
    return jsonify(videos)

@app.route('/api/videos', methods=['POST'])
def upload_video():
    data = request.get_json()
    video_id = f"video_{len(videos) + 1}"
    
    video = {
        'id': video_id,
        'title': data.get('title'),
        'description': data.get('description'),
        'creator_id': data.get('creator_id'),
        'creator_name': data.get('creator_name'),
        'thumbnail': '/api/placeholder-thumbnail',
        'video_url': '/api/placeholder-video',
        'duration': '10:30',
        'views': 0,
        'likes': 0,
        'dislikes': 0,
        'comments': [],
        'is_live': data.get('is_live', False)
    }
    
    videos.append(video)
    return jsonify(video)

@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if video:
        return jsonify(video)
    return jsonify({'error': 'Video not found'}), 404

@app.route('/api/videos/<video_id>/like', methods=['POST'])
def like_video(video_id):
    data = request.get_json()
    like_type = data.get('type')
    
    video = next((v for v in videos if v['id'] == video_id), None)
    if video:
        if like_type == 'like':
            video['likes'] += 1
        else:
            video['dislikes'] += 1
        return jsonify({'message': 'Success'})
    return jsonify({'error': 'Video not found'}), 404

@app.route('/api/videos/<video_id>/comments', methods=['POST'])
def add_comment(video_id):
    data = request.get_json()
    comment = {
        'id': f"comment_{len(videos)}",
        'username': data.get('username'),
        'text': data.get('text'),
        'created_at': '2024-01-01'
    }
    
    video = next((v for v in videos if v['id'] == video_id), None)
    if video:
        video['comments'].append(comment)
        return jsonify(comment)
    return jsonify({'error': 'Video not found'}), 404

@app.route('/api/placeholder-thumbnail')
def placeholder_thumbnail():
    # Return SVG placeholder
    svg = '''<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg">
    <rect width="320" height="180" fill="#333"/>
    <text x="160" y="90" fill="#666" text-anchor="middle" dy=".3em">Video Thumbnail</text>
    </svg>'''
    return svg, 200, {'Content-Type': 'image/svg+xml'}

@app.route('/api/placeholder-video')
def placeholder_video():
    return jsonify({'message': 'Video streaming not available on server'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'videos': len(videos)})

if __name__ == '__main__':
    # Add sample videos
    sample_videos = [
        {
            'id': 'sample1',
            'title': 'Welcome to Video Platform',
            'description': 'This is a sample video on our platform.',
            'creator_id': 'admin',
            'creator_name': 'Admin',
            'thumbnail': '/api/placeholder-thumbnail',
            'video_url': '/api/placeholder-video',
            'duration': '5:30',
            'views': 100,
            'likes': 10,
            'dislikes': 1,
            'comments': [],
            'is_live': False
        }
    ]
    videos.extend(sample_videos)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)