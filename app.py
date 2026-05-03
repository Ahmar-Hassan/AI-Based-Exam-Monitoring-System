# ---------------------------------------------------
# IMPORTS
# ---------------------------------------------------
import cv2
import time
import threading
import datetime
import os
import mysql.connector
import uuid

from datetime import timedelta
from flask import Flask, render_template, Response, jsonify, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from stream import StreamProcessor


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
class Config:
    DB_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "HASSAn#2005",
        "database": "ai_exam_monitoring"
    }

    SECRET_KEY = "super_secure_key"
    SNAPSHOT_DIR = "static/snapshots"
    REPORT_DIR = "static/reports"


app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

os.makedirs(Config.SNAPSHOT_DIR, exist_ok=True)
os.makedirs(Config.REPORT_DIR, exist_ok=True)


# ---------------------------------------------------
# DATABASE
# ---------------------------------------------------
def get_db():
    return mysql.connector.connect(**Config.DB_CONFIG)


# ---------------------------------------------------
# AUTH DECORATOR
# ---------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------
# SYSTEM STATE
# ---------------------------------------------------
class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_result = {}
        self.total_events = 0
        self.cheating_count = 0
        self.suspicious_count = 0

    def update(self, result):
        with self.lock:
            self.last_result = result

            if result["status"] == "CHEATING":
                self.cheating_count += 1
                self.total_events += 1
            elif result["status"] == "SUSPICIOUS":
                self.suspicious_count += 1
                self.total_events += 1


state = SystemState()


# ---------------------------------------------------
# CREATE SESSION (FIXED)
# ---------------------------------------------------
@app.route("/create_session", methods=["POST"])
@login_required
def create_session():
    try:
        name = request.form.get("name")
        description = request.form.get("description")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if not name or not start_time or not end_time:
            return "All fields required", 400

        start_dt = datetime.datetime.strptime(start_time, "%Y-%m-%d %I:%M %p")
        end_dt = datetime.datetime.strptime(end_time, "%Y-%m-%d %I:%M %p")

        if end_dt <= start_dt:
            return "Invalid time range", 400

        session_date = start_dt.date()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (name, description, session_date, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, description, session_date, start_dt, end_dt))

        conn.commit()
        cursor.close()
        conn.close()

        return "Session created"

    except mysql.connector.Error as e:
        if "Duplicate entry" in str(e):
            return "Session already exists", 400
        return str(e), 500


# ---------------------------------------------------
# SEARCH SESSION (NEW)
# ---------------------------------------------------
@app.route("/api/search_sessions")
@login_required
def search_sessions():

    query = request.args.get("q", "").strip()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM sessions
        WHERE name LIKE %s
           OR DATE_FORMAT(session_date, '%Y-%m-%d') LIKE %s
        ORDER BY created_at DESC
    """, (f"%{query}%", f"%{query}%"))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)


# ---------------------------------------------------
# PASSWORD RESET (NEW)
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():

    #  STEP 1: SHOW FORM
    if request.method == "GET":
        return render_template("password_reset.html", token=None)

    #  STEP 2: HANDLE FORM SUBMISSION
    email = request.form.get("email")

    if not email:
        return "Email is required", 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return "Email not found"

    token = str(uuid.uuid4())
    expiry = datetime.datetime.now() + timedelta(minutes=15)

    cursor.execute("""
        INSERT INTO password_resets (user_id, token, expires_at)
        VALUES (%s, %s, %s)
    """, (user["id"], token, expiry))

    conn.commit()
    cursor.close()
    conn.close()

    #  BETTER UX
    return redirect(f"/password_reset/{token}")

@app.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM password_resets
        WHERE token=%s AND expires_at > NOW()
    """, (token,))
    data = cursor.fetchone()

    if not data:
        return "Invalid or expired token"

    #  HANDLE PASSWORD SUBMIT
    if request.method == "POST":
        new_password = generate_password_hash(request.form.get("password"))

        cursor.execute("""
            UPDATE users SET password=%s WHERE id=%s
        """, (new_password, data["user_id"]))

        conn.commit()
        cursor.close()
        conn.close()

        return "Password updated successfully"

    #  IMPORTANT: SHOW FORM
    return render_template("password_reset.html", token=token)

# ---------------------------------------------------
# EVENT LOGGER
# ---------------------------------------------------
class EventLogger:
    def log(self, result, camera_id):

        if result["status"] == "NORMAL":
            return

        snapshot_path = None

        if result.get("frame") is not None:
            filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            path = os.path.join(Config.SNAPSHOT_DIR, filename)

            cv2.imwrite(path, result["frame"])
            snapshot_path = f"/{Config.SNAPSHOT_DIR}/{filename}"

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO events (camera_id, status, reason, score, snapshot)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            camera_id,
            result["status"],
            result["reason"],
            result["score"],
            snapshot_path
        ))

        conn.commit()
        cursor.close()
        conn.close()


logger = EventLogger()


# ---------------------------------------------------
# CAMERA STREAM
# ---------------------------------------------------
def generate_frames(camera_id, source):
    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    processor = StreamProcessor()

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame, result = processor.process_frame(frame)
        result["frame"] = frame

        state.update(result)
        logger.log(result, camera_id)

        _, buffer = cv2.imencode(".jpg", frame)

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() + b'\r\n')

    cap.release()


# ---------------------------------------------------
# PDF REPORT
# ---------------------------------------------------
def create_pdf(report, path):
    doc = SimpleDocTemplate(path)
    styles = getSampleStyleSheet()

    content = [
        Paragraph(f"Session: {report['session_name']}", styles['Title']),
        Paragraph(f"Date: {report['date']}", styles['Normal']),
        Paragraph(f"Total Events: {report['total_events']}", styles['Normal']),
        Spacer(1, 10)
    ]

    doc.build(content)


# ---------------------------------------------------
# AUTO REPORT
# ---------------------------------------------------
def auto_generate_reports():
    while True:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM sessions
            WHERE status='completed' AND report_generated=0
        """)

        sessions = cursor.fetchall()

        for s in sessions:
            report = {"session_name": s["name"], "date": str(s["session_date"]), "total_events": 0}

            filename = f"report_{s['id']}.pdf"
            path = os.path.join(Config.REPORT_DIR, filename)

            create_pdf(report, path)

            cursor.execute("""
                UPDATE sessions
                SET report_generated=1, report_path=%s
                WHERE id=%s
            """, (f"/{Config.REPORT_DIR}/{filename}", s["id"]))

        conn.commit()
        cursor.close()
        conn.close()

        time.sleep(20)


# ---------------------------------------------------
# SESSION SCHEDULER
# ---------------------------------------------------
def session_scheduler():
    while True:
        conn = get_db()
        cursor = conn.cursor()

        now = datetime.datetime.now()

        cursor.execute("UPDATE sessions SET status='active' WHERE start_time<=%s AND end_time>=%s",(now,now))
        cursor.execute("UPDATE sessions SET status='completed' WHERE end_time<%s",(now,))

        conn.commit()
        cursor.close()
        conn.close()

        time.sleep(30)


# ---------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email=%s",(request.form["email"],))
        if cursor.fetchone():
            return "Email exists"

        cursor.execute("INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                       (request.form["name"], request.form["email"],
                        generate_password_hash(request.form["password"])))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    
    if "user_id" in session:
        return redirect("/")

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            return "Email and password required", 400

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        #  Verify password
        if user and check_password_hash(user["password"], password):

            
            session.clear()                      
            session["user_id"] = user["id"]
            session.permanent = False           

            return redirect("/")

        return "Invalid credentials", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/video_feed/<int:camera_id>")
@login_required
def video_feed(camera_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM cameras WHERE id=%s",(camera_id,))
    cam = cursor.fetchone()

    cursor.close()
    conn.close()

    return Response(generate_frames(camera_id, cam["source"]),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------
# APIs
# ---------------------------------------------------
@app.route("/api/logs")
@login_required
def api_logs():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 50")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)


@app.route("/api/snapshots")
@login_required
def api_snapshots():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT snapshot FROM events WHERE snapshot IS NOT NULL")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([d["snapshot"] for d in data])


@app.route("/api/sessions")
@login_required
def api_sessions():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            id,
            name,
            description,
            DATE_FORMAT(session_date, '%d %b %Y') AS session_date,
            DATE_FORMAT(start_time, '%h:%i %p') AS start_time,
            DATE_FORMAT(end_time, '%h:%i %p') AS end_time,
            status,
            report_path
        FROM sessions
        ORDER BY created_at DESC
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

# ---------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------
@app.route("/download_report/<int:session_id>")
@login_required
def download_report(session_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT report_path FROM sessions WHERE id=%s",(session_id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data or not data["report_path"]:
        return "Report not ready"

    return send_file("." + data["report_path"], as_attachment=True)


# ---------------------------------------------------
# THREADS
# ---------------------------------------------------
threading.Thread(target=session_scheduler, daemon=True).start()
threading.Thread(target=auto_generate_reports, daemon=True).start()


# ---------------------------------------------------
# RUN
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)