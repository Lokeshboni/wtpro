from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

def create_user(users_collection, username, password):
    existing = users_collection.find_one({"username": username})
    if existing:
        return None
    hashed_pw = generate_password_hash(password)
    user = {"username": username, "password": hashed_pw}
    result = users_collection.insert_one(user)
    return str(result.inserted_id)

def verify_user(users_collection, username, password):
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user['password'], password):
        return str(user['_id'])
    return None

def get_username(users_collection, user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    return user['username'] if user else "Unknown"
