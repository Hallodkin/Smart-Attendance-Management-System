from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
import sqlite3
from datetime import datetime
import os
import time
import cv2
import dlib
import shutil
import numpy as np
import subprocess

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')  # Ensure you have a secret key set
app.config['SESSION_TYPE'] = 'filesystem'


# Sign Up Page
@app.route('/sign_up')
def sign_up():
    return render_template('signUpAdmin.html')

# Sign Up Process
def signup_admin(username, password):

    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO admin (username, password)
            VALUES (?, ?)
        ''', (username, password))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Admin already exists.", "danger")
        return False
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return False
    finally:
        conn.close()

    return True

@app.route('/signup_admin_action', methods=['POST'])
def signup_admin_action():
    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    # Check if password and confirm_password match
    if password != confirm_password:
        flash("Passwords do not match!", "danger")
        return redirect(url_for('sign_up'))

    # Call signup_admin function to perform registration
    registration_successful = signup_admin(username, password)

    if registration_successful:
        flash(f"Admin ({username}) registered successfully!", "success")
    else:
        flash("Registration failed. Please try again.", "danger")

    return redirect(url_for('sign_up'))

# Login Process (index)
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=25)])
    submit = SubmitField('Login')

@app.route('/', methods=['GET', 'POST'])
def index():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Query the database to check credentials
        try:
            conn = sqlite3.connect('attendance.db')
            cursor = conn.cursor()
            cursor.execute('SELECT password FROM admin WHERE username = ?', (username,))
            admin = cursor.fetchone()

            if admin and admin[0] == password:
                session['username'] = username
                return redirect(url_for('track_attendance_page'))
            else:
                flash('Invalid username or password', 'danger')
        except Exception as e:
            flash(f"An error occurred: {e}", 'danger')
        finally:
            conn.close()

    return render_template('login.html', form=form, selected_date='', no_data=False)

# Logout Process
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Track Attendance Page
@app.route('/track_attendance')
def track_attendance_page():
    if 'username' not in session:
        flash('You need to login first.', 'danger')
        return redirect(url_for('index'))
    return render_template('track_attendance.html', username=session["username"])

# Track Attendance Process
@app.route('/track_attendance_action', methods=['POST'])
def track_attendance_action():
    selected_date = request.form.get('selected_date')
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
    formatted_date = selected_date_obj.strftime('%Y-%m-%d')

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    cursor.execute("SELECT name, time FROM attendance WHERE date = ?", (formatted_date,))
    attendance_data = cursor.fetchall()

    conn.close()

    if not attendance_data:
        return render_template('track_attendance.html', selected_date=selected_date, no_data=True)

    return render_template('track_attendance.html', selected_date=selected_date, attendance_data=attendance_data)

# Employee List Page
@app.route('/employee_list')
def employee_list():
    if 'username' not in session:
        flash('You need to login first.', 'danger')
        return redirect(url_for('index'))

    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM employee")
        employees = cursor.fetchall()
        conn.close()

        employee_data = []
        for idx, emp in enumerate(employees):
            emp_id = emp[0]
            employee_data.append((emp_id, emp[1], emp[2], emp[3], emp[4], emp[5], emp[6], emp[7], emp[8]))

        if not employee_data:
            flash("No employee data available.",'warning')
            return render_template('manage_employee.html', employees=[], no_data=True)

        return render_template('manage_employee.html', employees=employee_data, no_data=False)

    except Exception as e:
        flash(f"An error occurred: {e}")
        return render_template('manage_employee.html', employees=[], no_data=True)

# Update Employee Page
@app.route('/update_employee', methods=['GET'])
def update_employee():
    if 'username' not in session:
        flash('You need to login first.', 'danger')
        return redirect(url_for('index'))

    employee_id = request.args.get('employee_id')
    if employee_id:
        employee = get_employee_by_id(employee_id)
        if employee:
            return render_template('update_employee.html', employee=employee)
        flash('Employee not found', 'danger')
    return redirect(url_for('employee_list'))

# Update Employee Process
@app.route('/update_employee_action', methods=['POST'])
def update_employee_action():
    employee_data = {
        'employee_id': request.form['employee_id'],
        'name': request.form['name'],
        'email': request.form['email'],
        'phone_number': request.form['phone_number'],
        'ic_number': request.form['ic_number'],
        'leave_balance': request.form['leave_balance'],
        'designation': request.form['designation'],
        'department': request.form['department']
    }

    if update_employee_in_db(**employee_data):
        flash('Employee updated successfully', 'success')
        return redirect(url_for('employee_list'))
    else:
        flash('Failed to update employee', 'danger')
        return redirect(url_for('update_employee', employee_id=employee_data['employee_id']))


# Get Employee by ID from Database
def get_employee_by_id(employee_id):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employee WHERE employee_id = ?', (employee_id,))
    employee = cursor.fetchone()
    conn.close()
    if employee:
        # Convert the tuple to a dictionary for easier access in templates
        employee_dict = {
            'employee_id': employee[0],
            'name': employee[1],
            'email': employee[2],
            'phone_number': employee[3],
            'ic_number': employee[4],
            'leave_balance': employee[5],
            'designation': employee[6],
            'department': employee[7]
        }
        return employee_dict
    return None

# Update Employee Information in Database
def update_employee_in_db(employee_id, name, email, phone_number, ic_number, leave_balance, designation, department):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE employee 
        SET name = ?, email = ?, phone_number = ?, ic_number = ?, leave_balance = ?, 
            designation = ?, department = ? 
        WHERE employee_id = ?
    ''', (name, email, phone_number, ic_number, leave_balance, designation, department, employee_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated > 0

# Delete Employee Page
@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    employee_id = request.form['employee_id']

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    # Get employee information before delete
    cursor.execute('SELECT folder_name FROM employee WHERE employee_id = ?', (employee_id,))
    result = cursor.fetchone()
    if result:
        folder_name = result[0]
    else:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employee_list'))

    try:
        # Delete employee record from database
        cursor.execute('DELETE FROM employee WHERE employee_id = ?', (employee_id,))
        conn.commit()

        # Delete employee's folder if it exists
        if folder_name:
            folder_path = os.path.join('data/data_faces_from_camera', folder_name)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)

        flash('Employee deleted successfully!', 'success')
        subprocess.run(['python', 'features_extraction_to_csv.py'])
    except Exception as e:
        flash(f"An error occurred while deleting employee: {e}", 'danger')
    finally:
        conn.close()

    return redirect(url_for('employee_list'))


# Register Employee Page
@app.route('/register_employee')
def register_employee_page():
    if 'username' not in session:
        flash('You need to login first.', 'danger')
        return redirect(url_for('index'))
    return render_template('register_employee.html')

# Register Employee Process
def register_employee(employee_id, name, email, phone_number, ic_number, leave_balance, designation, department, folder_name):

    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employee (
                employee_id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone_number TEXT,
                ic_number TEXT,
                leave_balance INTEGER,
                designation TEXT,
                department TEXT,
                folder_name TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO employee (employee_id, name, email, phone_number, ic_number, leave_balance, designation, department, folder_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, name, email, phone_number, ic_number, leave_balance, designation, department, folder_name))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Employee ID already exists.")
        return False
    except Exception as e:
        flash(f"An error occurred: {e}")
        return False
    finally:
        conn.close()

    return True

@app.route('/register_employee_action', methods=['POST'])
def register_employee_action():
    employee_id = request.form['employee_id']
    name = request.form['name']
    email = request.form['email']
    phone_number = request.form['phone_number']
    ic_number = request.form['ic_number']
    leave_balance = request.form['leave_balance']
    designation = request.form['designation']
    department = request.form['department']
    folder_name = ""

    # Call register_employee function to perform registration
    registration_successful = register_employee(employee_id, name, email, phone_number, ic_number, leave_balance, designation, department, folder_name)

    session['employee_id'] = employee_id
    session['name'] = name

    if registration_successful:
        flash("Employee (ID : " +employee_id+ ") registered successfully!")

    return redirect(url_for('face_register_page'))

# Face Register Page
@app.route('/face_register')
def face_register_page():
    if 'username' not in session:
        flash('You need to login first.', 'danger')
        return redirect(url_for('index'))

    face_register.initialize_camera()
    return render_template('register_face.html')

# Initialize Dlib's face detector
detector = dlib.get_frontal_face_detector()

# Face Register Process
class FaceRegister:
    def __init__(self):
        self.current_frame_faces_cnt = 0
        self.existing_faces_cnt = 0
        self.ss_cnt = 0
        self.input_name_char = ""
        self.path_photos_from_camera = "data/data_faces_from_camera/"
        self.current_face_dir = ""
        self.current_frame = None
        self.face_ROI_image = None
        self.face_ROI_width_start = 0
        self.face_ROI_height_start = 0
        self.face_ROI_width = 0
        self.face_ROI_height = 0
        self.ww = 0
        self.hh = 0
        self.out_of_range_flag = False
        self.face_folder_created_flag = False
        self.frame_time = 0
        self.frame_start_time = 0
        self.fps = 0
        self.fps_show = 0
        self.start_time = time.time()
        self.cap = cv2.VideoCapture(0)
        self._initialize_directories()
        self._check_existing_faces_count()
        self.cap = None
        self.camera_active = False
        self.existing_faces_cnt = 0
        self.initialize_camera()

    def initialize_camera(self):
        """Initialize the camera."""
        if not self.camera_active:
            self.cap = cv2.VideoCapture(0)
            self.camera_active = True

    def release_camera(self):
        """Release the camera."""
        if self.camera_active:
            self.cap.release()
            self.camera_active = False

    def get_frame(self):
        """Capture and process a single frame from the video stream."""
        if not self.camera_active:
            self.initialize_camera()

        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (640, 480))
                frame = self._adjust_color_balance(frame)
                return True, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return False, None


    def _initialize_directories(self):
        """Initialize directories for storing face images."""
        os.makedirs(self.path_photos_from_camera, exist_ok=True)

    def _check_existing_faces_count(self):
        """Check the number of existing faces in the directory."""
        if os.listdir(self.path_photos_from_camera):
            person_list = os.listdir(self.path_photos_from_camera)
            person_num_list = [int(person.split('_')[1].split('_')[0]) for person in person_list if person.split('_')[1].split('_')[0].isdigit()]
            self.existing_faces_cnt = max(person_num_list) if person_num_list else 0
        else:
            self.existing_faces_cnt = 0

    def _update_fps(self):
        """Update frames per second (FPS) for video capture."""
        now = time.time()
        if int(self.start_time) != int(now):
            self.fps_show = self.fps
        self.start_time = now
        self.frame_time = now - self.frame_start_time
        self.fps = 1.0 / self.frame_time if self.frame_time > 0 else float('inf')
        self.frame_start_time = now

    def create_face_folder(self):
        """Create a new folder for storing face images."""
        self.existing_faces_cnt += 1
        folder_name = f"{self.input_name_char}" if self.input_name_char else f"person_{self.existing_faces_cnt}"
        self.current_face_dir = os.path.join(self.path_photos_from_camera, folder_name)
        os.makedirs(self.current_face_dir, exist_ok=True)
        self.ss_cnt = 0
        self.face_folder_created_flag = True

    def save_current_face(self):
        """Save the current face ROI image to the folder."""
        if self.face_folder_created_flag:
            if self.current_frame_faces_cnt == 1 and not self.out_of_range_flag:
                self.ss_cnt += 1
                self.face_ROI_image = np.zeros((self.face_ROI_height * 2, self.face_ROI_width * 2, 3), np.uint8)
                for ii in range(self.face_ROI_height * 2):
                    for jj in range(self.face_ROI_width * 2):
                        self.face_ROI_image[ii][jj] = self.current_frame[self.face_ROI_height_start - self.hh + ii][self.face_ROI_width_start - self.ww + jj]
                self.face_ROI_image = cv2.cvtColor(self.face_ROI_image, cv2.COLOR_BGR2RGB)
                image_path = os.path.join(self.current_face_dir, f"img_face_{self.ss_cnt}.jpg")
                cv2.imwrite(image_path, self.face_ROI_image)
                return f"Face image saved at {image_path}"
            else:
                return "No face in current frame or out of range!"
        else:
            return "Please create a face folder first!"

    def get_frame(self):
        """Capture and process a single frame from the video stream."""
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (640, 480))
                frame = self._adjust_color_balance(frame)
                return True, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return False, None

    def _adjust_color_balance(self, frame):
        """Adjust the color balance of the frame."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.equalizeHist(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def process_frame(self):
        """Process the current frame to detect faces and update FPS."""
        ret, self.current_frame = self.get_frame()
        if not ret:
            return None

        faces = detector(self.current_frame, 0)
        self._update_fps()
        if faces:
            for d in faces:
                self.face_ROI_width_start = d.left()
                self.face_ROI_height_start = d.top()
                self.face_ROI_height = d.bottom() - d.top()
                self.face_ROI_width = d.right() - d.left()
                self.hh = self.face_ROI_height // 2
                self.ww = self.face_ROI_width // 2
                if (d.right() + self.ww > 640 or d.bottom() + self.hh > 480 or d.left() - self.ww < 0 or d.top() - self.hh < 0):
                    self.out_of_range_flag = True
                    color_rectangle = (255, 0, 0)
                else:
                    self.out_of_range_flag = False
                    color_rectangle = (255, 255, 255)
                self.current_frame = cv2.rectangle(self.current_frame,
                                                   (d.left() - self.ww, d.top() - self.hh),
                                                   (d.right() + self.ww, d.bottom() + self.hh),
                                                   color_rectangle, 2)
            self.current_frame_faces_cnt = len(faces)
        _, jpeg = cv2.imencode('.jpg', self.current_frame)
        return jpeg.tobytes()

face_register = FaceRegister()

def gen():
    while True:
        frame = face_register.process_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

# Face Register functions

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/clear_data', methods=['POST'])
def clear_data():
    """Clear all stored face data and reset face count."""
    folders_rd = os.listdir(face_register.path_photos_from_camera)
    for folder in folders_rd:
        shutil.rmtree(os.path.join(face_register.path_photos_from_camera, folder))
    if os.path.isfile("data/features_all.csv"):
        os.remove("data/features_all.csv")
    face_register.existing_faces_cnt = 0
    return jsonify(status="Data cleared")


@app.route('/set_name', methods=['POST'])
def set_name():
    """Set the name for the current face being registered."""
    face_register.input_name_char = request.form['name']
    face_register.create_face_folder()

    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()

        # Update the folder_name in the employee table
        cursor.execute('''
            UPDATE employee SET folder_name = ? WHERE employee_id = ?
        ''', (face_register.input_name_char, session.get('employee_id')))

        conn.commit()
        conn.close()

        return jsonify(
            status="Folder name " + face_register.input_name_char + " has been created and updated in database")

    except Exception as e:
        return jsonify(status=f"Error updating folder name: {str(e)}"), 500


@app.route('/save_face', methods=['POST'])
def save_face():
    """Save the current face image."""
    result = face_register.save_current_face()
    return jsonify(status=result)

@app.route('/run_feature_extraction', methods=['POST'])
def run_feature_extraction():
    """Run the feature extraction script."""
    try:
        subprocess.run(["python", "features_extraction_to_csv.py"], check=True)
        return jsonify(status="Feature extraction script executed")
    except subprocess.CalledProcessError:
        return jsonify(status="Feature extraction script failed")

@app.route('/release_camera', methods=['POST'])
def release_camera():
    # Replace 'employee_id' and 'name' in the session
    session['employee_id'] = "EmployeeID"
    session['name'] = "Name"

    """Release the camera and cleanup resources."""
    face_register.release_camera()
    return jsonify(status="Camera released")

# Attendance Report Function

if __name__ == '__main__':
    app.run(debug=True)
