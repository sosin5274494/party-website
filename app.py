# -*- coding: utf-8 -*-
"""
阳光聚会圈 - Flask后端应用
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sunshine-party-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///party.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)

db = SQLAlchemy(app)

# ============== 数据库模型 ==============

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(50))
    avatar = db.Column(db.String(200), default='/static/default-avatar.svg')
    bio = db.Column(db.Text)  # 技能介绍
    # 能力数值
    alcohol_level = db.Column(db.Integer, default=5)  # 酒量 1-10
    weight = db.Column(db.Integer, default=70)  # 体重
    drink_sessions = db.Column(db.Integer, default=1)  # 能喝几场
    drink_hours = db.Column(db.Integer, default=2)  # 能喝几小时
    drink_days = db.Column(db.Integer, default=1)  # 能连续几天
    popularity = db.Column(db.Integer, default=5)  # 受欢迎度 1-10
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', backref='events')

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filetype = db.Column(db.String(20))  # photo/video
    description = db.Column(db.Text)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.relationship('User', foreign_keys=[uploader_id], backref='media')
    approver = db.relationship('User', foreign_keys=[approved_by])

class EventParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    event = db.relationship('Event', backref='participants')
    user = db.relationship('User', backref='participations')

# ============== 路由 ==============

@app.route('/')
def index():
    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('index.html', events=events)

@app.route('/members')
def members():
    users = User.query.all()
    return render_template('members.html', users=users)

@app.route('/member/<int:user_id>')
def member_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('member.html', user=user)

@app.route('/gallery')
def gallery():
    # 只显示审核通过的内容
    media_list = Media.query.filter_by(status='approved').order_by(Media.created_at.desc()).all()
    return render_template('gallery.html', media_list=media_list)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        file = request.files.get('file')
        description = request.form.get('description', '')
        
        if file and file.filename:
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            filetype = 'video' if filename.lower().endswith(('.mp4', '.avi', '.mov', '.webm')) else 'photo'
            
            media = Media(
                filename=filename,
                filetype=filetype,
                description=description,
                uploader_id=session['user_id'],
                status='pending'
            )
            db.session.add(media)
            db.session.commit()
            flash('上传成功！等待管理员审核', 'success')
            return redirect(url_for('gallery'))
    
    return render_template('upload.html')

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event.html', event=event)

@app.route('/event/create', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        event = Event(
            title=request.form['title'],
            content=request.form['content'],
            event_date=datetime.strptime(request.form['event_date'], '%Y-%m-%dT%H:%M'),
            location=request.form['location'],
            creator_id=session['user_id']
        )
        db.session.add(event)
        db.session.commit()
        flash('聚会创建成功！', 'success')
        return redirect(url_for('index'))
    
    return render_template('create_event.html')

@app.route('/event/<int:event_id>/join')
def join_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event = Event.query.get_or_404(event_id)
    
    # 检查是否已参加
    existing = EventParticipant.query.filter_by(
        event_id=event_id, 
        user_id=session['user_id']
    ).first()
    
    if not existing:
        participant = EventParticipant(event_id=event_id, user_id=session['user_id'])
        db.session.add(participant)
        db.session.commit()
        flash('报名成功！', 'success')
    
    return redirect(url_for('event_detail', event_id=event_id))

# ============== 认证 ==============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:  # 生产环境应使用哈希
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nickname = request.form.get('nickname', username)
        
        # 检查用户名是否存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('register'))
        
        # 能力数值
        alcohol_level = int(request.form.get('alcohol_level', 5))
        weight = int(request.form.get('weight', 70))
        drink_sessions = int(request.form.get('drink_sessions', 1))
        drink_hours = int(request.form.get('drink_hours', 2))
        drink_days = int(request.form.get('drink_days', 1))
        popularity = int(request.form.get('popularity', 5))
        
        user = User(
            username=username,
            password=password,
            nickname=nickname,
            bio=request.form.get('bio', ''),
            alcohol_level=alcohol_level,
            weight=weight,
            drink_sessions=drink_sessions,
            drink_hours=drink_hours,
            drink_days=drink_days,
            popularity=popularity
        )
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.nickname = request.form.get('nickname', user.nickname)
        user.bio = request.form.get('bio', user.bio)
        user.alcohol_level = int(request.form.get('alcohol_level', user.alcohol_level))
        user.weight = int(request.form.get('weight', user.weight))
        user.drink_sessions = int(request.form.get('drink_sessions', user.drink_sessions))
        user.drink_hours = int(request.form.get('drink_hours', user.drink_hours))
        user.drink_days = int(request.form.get('drink_days', user.drink_days))
        user.popularity = int(request.form.get('popularity', user.popularity))
        
        # 处理头像上传
        avatar = request.files.get('avatar')
        if avatar and avatar.filename:
            filename = secure_filename(f"avatar_{user.id}_{avatar.filename}")
            avatar.save(os.path.join('static/avatars', filename))
            user.avatar = f'/static/avatars/{filename}'
        
        db.session.commit()
        flash('资料更新成功！', 'success')
    
    return render_template('profile.html', user=user)

# ============== 管理后台 ==============

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))
    
    pending_media = Media.query.filter_by(status='pending').all()
    return render_template('admin.html', media_list=pending_media)

@app.route('/admin/approve/<int:media_id>')
def approve_media(media_id):
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    media = Media.query.get_or_404(media_id)
    media.status = 'approved'
    media.approved_by = session['user_id']
    db.session.commit()
    flash('审核通过！', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/reject/<int:media_id>')
def reject_media(media_id):
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    media = Media.query.get_or_404(media_id)
    media.status = 'rejected'
    media.approved_by = session['user_id']
    db.session.commit()
    flash('已拒绝', 'success')
    return redirect(url_for('admin'))

# ============== 初始化 ==============

def init_db():
    with app.app_context():
        db.create_all()
        # 创建管理员账号
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password='admin123',
                nickname='管理员',
                is_admin=True,
                bio='网站管理员'
            )
            db.session.add(admin)
            db.session.commit()
            print("管理员账号已创建: admin / admin123")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    init_db()
    app.run(host='0.0.0.0', port=port, debug=False)
