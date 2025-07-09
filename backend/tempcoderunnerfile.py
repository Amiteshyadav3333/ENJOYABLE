from app import app, socketio, db

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables are created
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)