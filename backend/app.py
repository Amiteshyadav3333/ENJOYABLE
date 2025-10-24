import os
import cv2
from flask import Flask, request, jsonify, send_from_directory, Response, render_template
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
    try:
        data = request.get_json()
        username = data.get('username') if data else None
        password = data.get('password') if data else None
        
        if username in users and users[username] == password:
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': 1,
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

# Global video capture (0 = default webcam)
camera = cv2.VideoCapture(0)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            # Yield frame in byte format for MJPEG streaming
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    # Video streaming route
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(debug=True, port=5001)  # change to 5001 or any free port