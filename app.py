from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
import os

# Load environment variables
load_dotenv()

# Initialize app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Database
client = MongoClient(os.getenv("MONGO_URI"))
db = client.personal_wiki
entries = db.entries
users = db.users

# Home Page
@app.route('/')
def index():
    if "user_id" not in session:
        flash("Please login to view entries.", "info")
        return redirect(url_for("login"))

    all_entries = entries.find()
    return render_template('index.html', entries=all_entries)

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if users.find_one({"username": username}):
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))
        hashed_pw = generate_password_hash(password)
        users.insert_one({"username": username, "password": hashed_pw})
        user = users.find_one({"username": username})
        session["user_id"] = str(user["_id"])
        session["username"] = username
        flash("Registered successfully!", "success")
        return redirect(url_for("index"))
    return render_template("register.html")

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = username
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("login.html")

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

# Create Entry
@app.route('/create', methods=['GET', 'POST'])
def create_entry():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        topic = request.form['topic']
        tags = request.form['tags'].split(',') if request.form['tags'] else []

        image_files = request.files.getlist('images')
        video_files = request.files.getlist('videos')

        image_filenames = []
        for image in image_files:
            if image.filename:
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filenames.append(filename)

        video_filenames = []
        for video in video_files:
            if video.filename:
                filename = secure_filename(video.filename)
                video.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                video_filenames.append(filename)

        entry = {
            'title': title,
            'content': content,
            'topic': topic,
            'tags': tags,
            'images': image_filenames,
            'videos': video_filenames,
            'comments': [],
            'likes': [],  # initialize likes
            'user_id': session["user_id"],
            'username': session["username"]
        }
        entries.insert_one(entry)
        flash("Entry created successfully!", "success")
        return redirect(url_for('index'))

    return render_template('create_entry.html')

# View Entry
@app.route('/entry/<entry_id>')
def view_entry(entry_id):
    entry = entries.find_one({'_id': ObjectId(entry_id)})
    return render_template('view_entry.html', entry=entry)

# Edit Entry
@app.route('/entry/<entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    entry = entries.find_one({'_id': ObjectId(entry_id)})
    if not entry or entry['user_id'] != session.get('user_id'):
        flash("Unauthorized.", "danger")
        return redirect(url_for("index"))

    if request.method == 'POST':
        updated_data = {
            "title": request.form['title'],
            "content": request.form['content'],
            "topic": request.form['topic'],
            "tags": request.form['tags'].split(',') if request.form['tags'] else []
        }
        entries.update_one({'_id': ObjectId(entry_id)}, {'$set': updated_data})
        flash("Entry updated.", "success")
        return redirect(url_for('view_entry', entry_id=entry_id))

    return render_template("edit_entry.html", entry=entry)

# Delete Entry
@app.route('/entry/<entry_id>/delete')
def delete_entry(entry_id):
    entry = entries.find_one({'_id': ObjectId(entry_id)})
    if entry and entry['user_id'] == session.get('user_id'):
        entries.delete_one({'_id': ObjectId(entry_id)})
        flash("Entry deleted.", "info")
    else:
        flash("Unauthorized.", "danger")
    return redirect(url_for("index"))

# Add Comment
@app.route('/entry/<entry_id>/comment', methods=['POST'])
def add_comment(entry_id):
    if "username" not in session:
        return redirect(url_for("login"))

    comment_text = request.form["comment"]
    username = session["username"]

    entries.update_one(
        {"_id": ObjectId(entry_id)},
        {
            "$push": {
                "comments": {
                    "username": username,
                    "comment": comment_text,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            }
        }
    )
    flash("Comment added!", "success")
    return redirect(url_for("view_entry", entry_id=entry_id))

# Like Entry
@app.route('/entry/<entry_id>/like', methods=['POST'])
def like_entry(entry_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id = session["user_id"]
    entry = entries.find_one({'_id': ObjectId(entry_id)})
    if not entry:
        return jsonify({"success": False, "message": "Entry not found"}), 404

    if user_id in entry.get("likes", []):
        entries.update_one({"_id": ObjectId(entry_id)}, {"$pull": {"likes": user_id}})
        liked = False
    else:
        entries.update_one({"_id": ObjectId(entry_id)}, {"$addToSet": {"likes": user_id}})
        liked = True

    updated_entry = entries.find_one({'_id': ObjectId(entry_id)})
    like_count = len(updated_entry.get("likes", []))
    return jsonify({"success": True, "liked": liked, "like_count": like_count})

# Inject user context
@app.context_processor
def inject_user():
    return dict(current_user=session.get("username"))

# Run app
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

