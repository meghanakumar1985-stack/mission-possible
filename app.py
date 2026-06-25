from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "missionpossible2024secret"

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DATA_FILE = "data.json"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PRIORITY_POINTS = {"high": 5, "medium": 3, "low": 1}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "tasks": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_leaderboard(data):
    scores = {}
    for uname, uinfo in data["users"].items():
        scores[uname] = {"display_name": uinfo["display_name"], "avatar": uinfo.get(
            "avatar"), "disney_char": uinfo.get("disney_char", ""), "points": 0, "completed": 0}
    for task in data["tasks"]:
        owner = task["owner"]
        if task.get("status") == "completed" and owner in scores:
            scores[owner]["points"] += PRIORITY_POINTS.get(
                task.get("priority", "low"), 1)
            scores[owner]["completed"] += 1
    return sorted(scores.values(), key=lambda x: x["points"], reverse=True)


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = load_data()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        display_name = request.form.get("display_name", "").strip()
        disney_char = request.form.get("disney_char", "").strip()
        role = request.form.get("role", "member")

        if not username or not password or not display_name:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))
        if username in data["users"]:
            flash("Username already taken.", "error")
            return redirect(url_for("register"))

        avatar = None
        if "avatar" in request.files:
            file = request.files["avatar"]
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()
                filename = f"{username}_{uuid.uuid4().hex[:8]}.{ext}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                avatar = filename

        data["users"][username] = {
            "password": password,
            "display_name": display_name,
            "disney_char": disney_char,
            "avatar": avatar,
            "role": role,
            "joined": datetime.now().strftime("%Y-%m-%d")
        }
        save_data(data)
        flash("Welcome to Mission Possible! 🎯", "success")
        session["username"] = username
        session["role"] = role
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = load_data()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        user = data["users"].get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user.get("role", "member")
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    username = session["username"]
    # Delete user's avatar file
    user = data["users"].get(username, {})
    if user.get("avatar"):
        avatar_path = os.path.join(app.config["UPLOAD_FOLDER"], user["avatar"])
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
    # Delete user and their tasks
    data["users"].pop(username, None)
    data["tasks"] = [t for t in data["tasks"] if t["owner"] != username]
    save_data(data)
    session.clear()
    flash("Your account has been deleted. Goodbye! 👋", "success")
    return redirect(url_for("login"))


@app.route("/delete_member/<target_username>")
def delete_member(target_username):
    if "username" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "manager":
        flash("Only managers can delete accounts.", "error")
        return redirect(url_for("dashboard"))
    data = load_data()
    user = data["users"].get(target_username, {})
    if user.get("avatar"):
        avatar_path = os.path.join(app.config["UPLOAD_FOLDER"], user["avatar"])
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
    data["users"].pop(target_username, None)
    data["tasks"] = [t for t in data["tasks"] if t["owner"] != target_username]
    save_data(data)
    flash(f"Account @{target_username} has been removed. 🗑️", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    username = session["username"]
    role = session.get("role", "member")
    user = data["users"].get(username, {})
    users = data["users"]

    my_tasks = [t for t in data["tasks"] if t["owner"] == username]
    team_tasks = {}
    for uname, uinfo in users.items():
        if uname != username:
            utasks = [t for t in data["tasks"] if t["owner"] == uname]
            team_tasks[uname] = {"info": uinfo, "tasks": utasks}

    leaderboard = get_leaderboard(data)
    return render_template("dashboard.html",
                           user=user, username=username, role=role,
                           my_tasks=my_tasks, team_tasks=team_tasks,
                           users=users, leaderboard=leaderboard)


@app.route("/leaderboard")
def leaderboard():
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    username = session["username"]
    user = data["users"].get(username, {})
    board = get_leaderboard(data)
    return render_template("leaderboard.html", board=board, user=user, username=username, role=session.get("role", "member"))


@app.route("/add_task", methods=["POST"])
def add_task():
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    text = request.form.get("task", "").strip()
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date", "")
    assigned_to = request.form.get("assigned_to", session["username"])

    # members can only assign to themselves
    if session.get("role") != "manager":
        assigned_to = session["username"]

    if text:
        data["tasks"].append({
            "id": str(uuid.uuid4()),
            "owner": assigned_to,
            "assigned_by": session["username"],
            "text": text,
            "priority": priority,
            "due_date": due_date,
            "status": "not_started",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_data(data)
    return redirect(url_for("dashboard"))


@app.route("/status/<task_id>/<new_status>")
def change_status(task_id, new_status):
    if "username" not in session:
        return redirect(url_for("login"))
    if new_status not in ["not_started", "in_progress", "completed"]:
        return redirect(url_for("dashboard"))
    data = load_data()
    role = session.get("role", "member")
    for task in data["tasks"]:
        if task["id"] == task_id:
            if task["owner"] == session["username"] or role == "manager":
                task["status"] = new_status
                break
    save_data(data)
    return redirect(url_for("dashboard"))


@app.route("/delete/<task_id>")
def delete_task(task_id):
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    role = session.get("role", "member")
    data["tasks"] = [t for t in data["tasks"]
                     if not (t["id"] == task_id and (t["owner"] == session["username"] or role == "manager"))]
    save_data(data)
    return redirect(url_for("dashboard"))


@app.route("/edit/<task_id>", methods=["POST"])
def edit_task(task_id):
    if "username" not in session:
        return redirect(url_for("login"))
    data = load_data()
    role = session.get("role", "member")
    new_text = request.form.get("text", "").strip()
    new_priority = request.form.get("priority", "medium")
    new_due = request.form.get("due_date", "")
    new_status = request.form.get("status", "not_started")
    for task in data["tasks"]:
        if task["id"] == task_id and (task["owner"] == session["username"] or role == "manager"):
            if new_text:
                task["text"] = new_text
            task["priority"] = new_priority
            task["due_date"] = new_due
            task["status"] = new_status
            break
    save_data(data)
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
