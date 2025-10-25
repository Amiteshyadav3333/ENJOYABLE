import os
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'production-video-platform-key'
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create upload directory
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Storage
users = {'admin': 'admin123', 'creator1': 'pass123', 'user1': 'user123'}
videos = []
comments = []
likes = []
live_streams = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return send_from_directory('../frontend', 'production_platform.html')

# Authentication
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

# Video Management
@app.route('/api/videos', methods=['GET'])
def get_videos():
    enhanced_videos = []
    for video in videos:
        video_likes = len([l for l in likes if l['video_id'] == video['id'] and l['type'] == 'like'])
        video_dislikes = len([l for l in likes if l['video_id'] == video['id'] and l['type'] == 'dislike'])
        video_comments = [c for c in comments if c['video_id'] == video['id']]
        
        enhanced_videos.append({
            **video,
            'likes': video_likes,
            'dislikes': video_dislikes,
            'comments_count': len(video_comments)
        })
    
    return jsonify(enhanced_videos)

@app.route('/api/upload-video', methods=['POST'])
def upload_video():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        title = request.form.get('title')
        description = request.form.get('description')
        creator_id = request.form.get('creator_id')
        creator_name = request.form.get('creator_name')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: mp4, avi, mov, wmv, flv, webm, mkv'}), 400
        
        # Generate unique filename
        video_id = str(uuid.uuid4())
        filename = secure_filename(f"{video_id}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(filepath)
        
        # Create video record
        video = {
            'id': video_id,
            'title': title or 'Untitled Video',
            'description': description or '',
            'creator_id': creator_id,
            'creator_name': creator_name,
            'filename': filename,
            'filepath': filepath,
            'thumbnail': f'/api/videos/{video_id}/thumbnail',
            'video_url': f'/api/videos/{video_id}/stream',
            'duration': 'Unknown',
            'views': 0,
            'created_at': datetime.now().isoformat(),
            'is_live': False,
            'file_size': os.path.getsize(filepath)
        }
        
        videos.append(video)
        return jsonify({'message': 'Video uploaded successfully', 'video': video})
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/videos/<video_id>/stream')
def stream_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    # Increment view count
    video['views'] += 1
    
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], video['filename'])
    except FileNotFoundError:
        return jsonify({'error': 'Video file not found'}), 404

@app.route('/api/videos/<video_id>/download')
def download_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], video['filename'], as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'Video file not found'}), 404

@app.route('/api/videos/<video_id>/thumbnail')
def get_thumbnail(video_id):
    # Generate SVG thumbnail with video info
    video = next((v for v in videos if v['id'] == video_id), None)
    title = video['title'][:20] + '...' if video and len(video['title']) > 20 else (video['title'] if video else 'Video')
    
    svg = f'''<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg">
    <rect width="320" height="180" fill="#1a1a1a"/>
    <rect x="10" y="10" width="300" height="160" fill="#333" rx="8"/>
    <circle cx="160" cy="90" r="30" fill="#ff0000"/>
    <polygon points="150,75 150,105 175,90" fill="white"/>
    <text x="160" y="140" fill="#fff" text-anchor="middle" font-size="12">{title}</text>
    <text x="160" y="160" fill="#aaa" text-anchor="middle" font-size="10">Click to play</text>
    </svg>'''
    return svg, 200, {'Content-Type': 'image/svg+xml'}

@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    video_likes = len([l for l in likes if l['video_id'] == video_id and l['type'] == 'like'])
    video_dislikes = len([l for l in likes if l['video_id'] == video_id and l['type'] == 'dislike'])
    video_comments = [c for c in comments if c['video_id'] == video_id]
    
    return jsonify({
        **video,
        'likes': video_likes,
        'dislikes': video_dislikes,
        'comments': video_comments
    })

@app.route('/api/videos/<video_id>/like', methods=['POST'])
def like_video(video_id):
    data = request.get_json()
    user_id = data.get('user_id')
    like_type = data.get('type')  # 'like' or 'dislike'
    
    # Remove existing like/dislike from this user
    global likes
    likes = [l for l in likes if not (l['video_id'] == video_id and l['user_id'] == user_id)]
    
    # Add new like/dislike
    likes.append({
        'video_id': video_id,
        'user_id': user_id,
        'type': like_type,
        'created_at': datetime.now().isoformat()
    })
    
    return jsonify({'message': f'{like_type.capitalize()} added successfully'})

@app.route('/api/videos/<video_id>/comments', methods=['POST'])
def add_comment(video_id):
    data = request.get_json()
    comment_id = str(uuid.uuid4())
    
    comment = {
        'id': comment_id,
        'video_id': video_id,
        'user_id': data.get('user_id'),
        'username': data.get('username'),
        'text': data.get('text'),
        'created_at': datetime.now().isoformat()
    }
    
    comments.append(comment)
    return jsonify(comment)

@app.route('/api/videos/<video_id>/comments/<comment_id>', methods=['DELETE'])
def delete_comment(video_id, comment_id):
    global comments
    comments = [c for c in comments if c['id'] != comment_id]
    return jsonify({'message': 'Comment deleted'})

@app.route('/api/videos/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    data = request.get_json()
    user_id = data.get('user_id')
    
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    # Only creator or admin can delete
    if video['creator_id'] != user_id and user_id != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete video file
    try:
        if os.path.exists(video['filepath']):
            os.remove(video['filepath'])
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    # Remove from database
    global videos, comments, likes
    videos = [v for v in videos if v['id'] != video_id]
    comments = [c for c in comments if c['video_id'] != video_id]
    likes = [l for l in likes if l['video_id'] != video_id]
    
    return jsonify({'message': 'Video deleted successfully'})

# Live Streaming
@app.route('/api/start-live', methods=['POST'])
def start_live():
    data = request.get_json()
    stream_id = str(uuid.uuid4())
    
    live_streams[stream_id] = {
        'id': stream_id,
        'title': data.get('title'),
        'description': data.get('description'),
        'creator_id': data.get('creator_id'),
        'creator_name': data.get('creator_name'),
        'viewers': 0,
        'started_at': datetime.now().isoformat(),
        'is_active': True,
        'chat_messages': []
    }
    
    return jsonify({
        'stream_id': stream_id,
        'message': 'Live stream started',
        'stream_url': f'/api/live/{stream_id}'
    })

@app.route('/api/live/<stream_id>')
def get_live_stream(stream_id):
    if stream_id not in live_streams:
        return jsonify({'error': 'Stream not found'}), 404
    
    live_streams[stream_id]['viewers'] += 1
    return jsonify(live_streams[stream_id])

@app.route('/api/live/<stream_id>/chat', methods=['POST'])
def add_live_chat(stream_id):
    if stream_id not in live_streams:
        return jsonify({'error': 'Stream not found'}), 404
    
    data = request.get_json()
    message = {
        'id': str(uuid.uuid4()),
        'username': data.get('username'),
        'text': data.get('text'),
        'timestamp': datetime.now().isoformat()
    }
    
    live_streams[stream_id]['chat_messages'].append(message)
    return jsonify(message)

@app.route('/api/stop-live/<stream_id>', methods=['POST'])
def stop_live(stream_id):
    if stream_id not in live_streams:
        return jsonify({'error': 'Stream not found'}), 404
    
    # Save as video
    stream_data = live_streams[stream_id]
    video = {
        'id': stream_id,
        'title': stream_data['title'],
        'description': stream_data['description'],
        'creator_id': stream_data['creator_id'],
        'creator_name': stream_data['creator_name'],
        'thumbnail': f'/api/videos/{stream_id}/thumbnail',
        'video_url': f'/api/videos/{stream_id}/stream',
        'duration': 'Live Recording',
        'views': stream_data['viewers'],
        'created_at': stream_data['started_at'],
        'is_live': False,
        'was_live': True
    }
    
    videos.append(video)
    del live_streams[stream_id]
    
    return jsonify({'message': 'Stream stopped and saved'})

@app.route('/api/live-streams', methods=['GET'])
def get_live_streams():
    return jsonify(list(live_streams.values()))

# Share functionality
@app.route('/api/videos/<video_id>/share', methods=['POST'])
def share_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    share_url = f"{request.host_url}watch/{video_id}"
    return jsonify({
        'share_url': share_url,
        'title': video['title'],
        'description': video['description']
    })

@app.route('/watch/<video_id>')
def watch_video(video_id):
    return send_from_directory('../frontend', 'watch.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'total_videos': len(videos),
        'total_users': len(users),
        'active_streams': len(live_streams),
        'total_comments': len(comments),
        'total_likes': len(likes)
    })

if __name__ == '__main__':
    # Add sample data
    sample_videos = [
        {
            'id': 'sample1',
            'title': '🎥 Welcome to Production Video Platform',
            'description': 'Complete video platform with upload, streaming, and live features.',
            'creator_id': 'admin',
            'creator_name': 'Admin',
            'thumbnail': '/api/videos/sample1/thumbnail',
            'video_url': '/api/videos/sample1/stream',
            'duration': '5:30',
            'views': 150,
            'created_at': datetime.now().isoformat(),
            'is_live': False,
            'file_size': 0
        }
    ]
    videos.extend(sample_videos)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)