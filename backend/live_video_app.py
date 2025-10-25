import os
import cv2
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import threading
import time

app = Flask(__name__)
app.secret_key = 'live-video-key'
CORS(app)

# Storage
users = {'admin': 'admin123', 'creator1': 'pass123'}
videos = []
live_streams = {}
camera = None

def init_camera():
    global camera
    try:
        # Try different camera indices
        for i in range(3):
            print(f"Trying camera index {i}...")
            camera = cv2.VideoCapture(i)
            if camera.isOpened():
                # Test if we can read a frame
                ret, frame = camera.read()
                if ret:
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    camera.set(cv2.CAP_PROP_FPS, 30)
                    print(f"✅ Camera {i} initialized successfully")
                    return True
                else:
                    camera.release()
            else:
                if camera:
                    camera.release()
        
        print("❌ No working camera found")
        camera = None
        return False
    except Exception as e:
        print(f"❌ Camera error: {e}")
        camera = None
        return False

def generate_frames(stream_id):
    global camera
    while stream_id in live_streams:
        if camera is None or not camera.isOpened():
            if not init_camera():
                time.sleep(1)
                continue
        
        success, frame = camera.read()
        if not success:
            print("Failed to read frame")
            time.sleep(0.1)
            continue
        
        # Add stream info overlay
        cv2.putText(frame, f"LIVE: {live_streams[stream_id]['title']}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Viewers: {live_streams[stream_id]['viewers']}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.033)  # ~30 FPS

@app.route('/')
def index():
    return send_from_directory('../frontend', 'live_platform.html')

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
        'is_active': True
    }
    
    # Initialize camera if not done
    if camera is None:
        init_camera()
    
    return jsonify({
        'stream_id': stream_id,
        'stream_url': f'/api/stream/{stream_id}',
        'message': 'Live stream started'
    })

@app.route('/api/stream/<stream_id>')
def video_stream(stream_id):
    if stream_id not in live_streams:
        return "Stream not found", 404
    
    # Increment viewer count
    live_streams[stream_id]['viewers'] += 1
    
    return Response(generate_frames(stream_id),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stop-live/<stream_id>', methods=['POST'])
def stop_live(stream_id):
    if stream_id in live_streams:
        # Save to videos
        stream_data = live_streams[stream_id]
        video = {
            'id': stream_id,
            'title': stream_data['title'],
            'description': stream_data['description'],
            'creator_id': stream_data['creator_id'],
            'creator_name': stream_data['creator_name'],
            'thumbnail': f'/api/videos/{stream_id}/thumbnail',
            'video_url': f'/api/videos/{stream_id}/playback',
            'duration': '00:00',
            'views': stream_data['viewers'],
            'likes': 0,
            'dislikes': 0,
            'comments': [],
            'created_at': stream_data['started_at'],
            'is_live': False
        }
        videos.append(video)
        
        # Remove from live streams
        del live_streams[stream_id]
        
        return jsonify({'message': 'Stream stopped and saved'})
    
    return jsonify({'error': 'Stream not found'}), 404

@app.route('/api/live-streams', methods=['GET'])
def get_live_streams():
    return jsonify(list(live_streams.values()))

@app.route('/api/videos', methods=['GET'])
def get_videos():
    all_videos = list(videos) + [
        {**stream, 'is_live': True, 'likes': 0, 'dislikes': 0, 'comments': []}
        for stream in live_streams.values()
    ]
    return jsonify(all_videos)

@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    # Check live streams first
    if video_id in live_streams:
        stream = live_streams[video_id]
        return jsonify({
            **stream,
            'is_live': True,
            'likes': 0,
            'dislikes': 0,
            'comments': []
        })
    
    # Check saved videos
    video = next((v for v in videos if v['id'] == video_id), None)
    if video:
        return jsonify(video)
    
    return jsonify({'error': 'Video not found'}), 404

@app.route('/api/videos/<video_id>/thumbnail')
def get_thumbnail(video_id):
    # Generate thumbnail from current frame
    if camera and camera.isOpened():
        ret, frame = camera.read()
        if ret:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    # Fallback placeholder
    return send_from_directory('../assets', 'placeholder.jpg')

@app.route('/api/camera-test')
def camera_test():
    if init_camera():
        return jsonify({'status': 'Camera working', 'available': True})
    else:
        return jsonify({'status': 'Camera not available', 'available': False})

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'camera_available': camera is not None and camera.isOpened(),
        'active_streams': len(live_streams),
        'total_videos': len(videos)
    })

if __name__ == '__main__':
    print("🎥 Starting Live Video Platform...")
    
    # Initialize camera on startup
    if init_camera():
        print("📹 Camera ready for streaming")
    else:
        print("⚠️  Camera not available - using placeholder")
    
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)