import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'video-platform-key'
CORS(app)

# In-memory storage
users = {'admin': 'admin123', 'creator1': 'pass123'}
videos = []
comments = []
likes = []

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

# Video Management
@app.route('/api/videos', methods=['GET'])
def get_videos():
    return jsonify([{
        **video,
        'likes': len([l for l in likes if l['video_id'] == video['id'] and l['type'] == 'like']),
        'dislikes': len([l for l in likes if l['video_id'] == video['id'] and l['type'] == 'dislike']),
        'comments_count': len([c for c in comments if c['video_id'] == video['id']])
    } for video in videos])

@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    
    video_comments = [c for c in comments if c['video_id'] == video_id]
    video_likes = len([l for l in likes if l['video_id'] == video_id and l['type'] == 'like'])
    video_dislikes = len([l for l in likes if l['video_id'] == video_id and l['type'] == 'dislike'])
    
    return jsonify({
        **video,
        'likes': video_likes,
        'dislikes': video_dislikes,
        'comments': video_comments
    })

@app.route('/api/videos', methods=['POST'])
def upload_video():
    data = request.get_json()
    video_id = str(uuid.uuid4())
    
    video = {
        'id': video_id,
        'title': data.get('title'),
        'description': data.get('description'),
        'creator_id': data.get('creator_id'),
        'creator_name': data.get('creator_name'),
        'thumbnail': f'/api/videos/{video_id}/thumbnail',
        'video_url': f'/api/videos/{video_id}/stream',
        'duration': '10:30',
        'views': 0,
        'created_at': datetime.now().isoformat(),
        'is_live': data.get('is_live', False)
    }
    
    videos.append(video)
    return jsonify(video)

@app.route('/api/videos/<video_id>/stream')
def stream_video(video_id):
    # Simulate video streaming - in production, serve actual video files
    return send_from_directory('../assets', 'sample_video.mp4')

@app.route('/api/videos/<video_id>/thumbnail')
def get_thumbnail(video_id):
    # Simulate thumbnail - in production, serve actual thumbnails
    return send_from_directory('../assets', 'thumbnail.jpg')

@app.route('/api/videos/<video_id>/like', methods=['POST'])
def like_video(video_id):
    data = request.get_json()
    user_id = data.get('user_id')
    like_type = data.get('type')  # 'like' or 'dislike'
    
    # Remove existing like/dislike
    global likes
    likes = [l for l in likes if not (l['video_id'] == video_id and l['user_id'] == user_id)]
    
    # Add new like/dislike
    likes.append({
        'video_id': video_id,
        'user_id': user_id,
        'type': like_type,
        'created_at': datetime.now().isoformat()
    })
    
    return jsonify({'message': f'{like_type} added successfully'})

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
    
    global videos, comments, likes
    videos = [v for v in videos if v['id'] != video_id]
    comments = [c for c in comments if c['video_id'] != video_id]
    likes = [l for l in likes if l['video_id'] != video_id]
    
    return jsonify({'message': 'Video deleted successfully'})

@app.route('/api/videos/<video_id>/download')
def download_video(video_id):
    # In production, serve actual video file for download
    return send_from_directory('../assets', 'sample_video.mp4', as_attachment=True)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Add sample videos
    sample_videos = [
        {
            'id': 'sample1',
            'title': 'Amazing Live Podcast Session',
            'description': 'Join us for an incredible discussion about technology and innovation.',
            'creator_id': 'admin',
            'creator_name': 'Admin User',
            'thumbnail': '/api/videos/sample1/thumbnail',
            'video_url': '/api/videos/sample1/stream',
            'duration': '15:42',
            'views': 1250,
            'created_at': datetime.now().isoformat(),
            'is_live': False
        },
        {
            'id': 'sample2',
            'title': 'Live Coding Session - Python Flask',
            'description': 'Building a video platform from scratch using Python and Flask.',
            'creator_id': 'creator1',
            'creator_name': 'Creator One',
            'thumbnail': '/api/videos/sample2/thumbnail',
            'video_url': '/api/videos/sample2/stream',
            'duration': '32:15',
            'views': 890,
            'created_at': datetime.now().isoformat(),
            'is_live': True
        }
    ]
    
    videos.extend(sample_videos)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)