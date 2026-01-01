import os
import io
import json
import base64
from datetime import datetime, UTC
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy 
from PIL import Image
import numpy as np
import face_recognition
from pyngrok import ngrok

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'users.db')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    salary = db.Column(db.String(50), nullable=True)
    face_encoding_json = db.Column(db.Text, nullable=True) 

    def get_encoding(self):
        if not self.face_encoding_json:
            return None
        return np.array(json.loads(self.face_encoding_json))

def save_base64_image(data_url, prefix='face'):
    header, encoded = data_url.split(',', 1)
    data = base64.b64decode(encoded)
    img = Image.open(io.BytesIO(data)).convert('RGB')
    filename = f"{prefix}_{int(datetime.now(UTC).timestamp())}.jpg"
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img.save(path, format='JPEG')
    return filename, path

def compare_encodings(enc1, enc2, tolerance=0.4):
    if enc1 is None or enc2 is None:
        return False
    dist = np.linalg.norm(enc1 - enc2)
    return (dist <= tolerance)
    
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('login'))   
 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        face_data = request.form.get('face_image', None)
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('البريد غير موجود. الرجاء إنشاء حساب أولًا.', 'danger')
            return redirect(url_for('register'))
        if not face_data:
            flash('الرجاء التقاط صورة الوجه.', 'danger')
            return redirect(url_for('login'))
        try:
            filename, path = save_base64_image(face_data, prefix='login')
            image = face_recognition.load_image_file(path)
            encs = face_recognition.face_encodings(image)
            if not encs:
                flash('لم يتم العثور على وجه واضح في الصورة. حاول مجددًا.', 'danger')
                return redirect(url_for('login'))
            login_encoding = encs[0]
            registered_encoding = user.get_encoding()
            match = compare_encodings(registered_encoding, login_encoding, tolerance=0.4)
            if match:
                session['user_id'] = user.id
                return redirect(url_for('profile'))
            else:
                flash('خطأ: الوجه غير مطابق: ' , 'danger')
                return redirect(url_for('login'))
        except :
            flash('حدث خطأ أثناء التحقق: ', 'danger')
            return redirect(url_for('login'))
        os.remove(path)    
    return render_template('login.html')
 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        dob = request.form.get('dob', '').strip()
        email = request.form.get('email', '').strip().lower()
        salary  = request.form.get('salary', '').strip()
        face_data = request.form.get('face_image', None)

        if not (name and dob and email and face_data):
            flash('الرجاء ملء الحقول المطلوبة .', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('هذا البريد مسجل مسبقًا. حاول تسجيل الدخول بدلاً من ذلك.', 'warning')
            return redirect(url_for('login'))
            
        try:
            filename, path = save_base64_image(face_data, prefix='reg')            
            image = face_recognition.load_image_file(path)
            encs = face_recognition.face_encodings(image)
            os.remove(path)
            if not encs:
                flash('لم يتم العثور على وجه واضح في الصورة. حاول مجددًا.', 'danger')
                return redirect(url_for('register'))
            if len(encs)>1:
                flash('يوجد اكثر من وجه بالصورة', 'danger')
                return redirect(url_for('register'))    
                
            encoding = encs[0].tolist()
            user = User(name=name, dob=dob, email=email, salary=salary , face_encoding_json=json.dumps(encoding))
            db.session.add(user)
            db.session.commit()
            flash('تم إنشاء الحساب بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
            return redirect(url_for('login'))
        except :
            flash('حدث خطأ: ', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('الرجاء تسجيل الدخول أولًا.', 'warning')
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        flash('المستخدم غير موجود.', 'danger')
        return redirect(url_for('login'))
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('تم تسجيل الخروج.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    #with app.app_context():
    #    db.create_all()
    public_url = ngrok.connect(5000)
    print("Ngrok URL:", public_url)
    app.run(host='0.0.0.0', port=5000, debug=False)
