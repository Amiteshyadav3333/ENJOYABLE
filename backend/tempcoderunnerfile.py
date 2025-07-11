@app.route('/signup', methods=['POST'])
# def signup():
#     data = request.get_json()
#     username = data.get('username')
#     password = data.get('password')
#     mobile = data.get('mobile')
#     is_admin = data.get('is_admin', False)
#     if User.query.filter_by(username=username).first():
#         return jsonify({"message": "Username already exists"}), 409
#     password_hash = generate_password_hash(password)
#     user = User(username=username, mobile=mobile, password_hash=password_hash, is_admin=is_admin)
#     db.session.add(user)
#     db.session.commit()
#     return jsonify({"message": "Signup successful"}), 201