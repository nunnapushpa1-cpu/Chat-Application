from flask import Flask, render_template, redirect, url_for, flash, jsonify, request
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = "secret123"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, manage_session=False)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ── Models ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email    = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class PrivateMessage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    edited      = db.Column(db.Boolean, default=False)
    deleted     = db.Column(db.Boolean, default=False)
    seen        = db.Column(db.Boolean, default=False)

    sender   = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Forms ─────────────────────────────────────────────────────────────────────

class SignupForm(FlaskForm):
    username         = StringField('Username', validators=[DataRequired()])
    email            = StringField('Email', validators=[DataRequired(), Email()])
    password         = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit           = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email    = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit   = SubmitField('Log In')


# ── Helper ────────────────────────────────────────────────────────────────────

def private_room(a, b):
    return f"pm_{min(a, b)}_{max(a, b)}"


# ── Socket Events ─────────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    join_room(f"user_{current_user.id}")

@socketio.on('join_chat')
def handle_join_chat(data):
    other_id = int(data['other_id'])
    room = private_room(current_user.id, other_id)
    join_room(room)

    messages = PrivateMessage.query.filter(
        db.or_(
            db.and_(PrivateMessage.sender_id == current_user.id,
                    PrivateMessage.receiver_id == other_id),
            db.and_(PrivateMessage.sender_id == other_id,
                    PrivateMessage.receiver_id == current_user.id)
        )
    ).order_by(PrivateMessage.timestamp.asc()).limit(50).all()

    history = []
    for m in messages:
        history.append({
            'id':        m.id,
            'sender_id': m.sender_id,
            'sender':    m.sender.username,
            'content':   '🚫 This message was deleted' if m.deleted else m.content,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'edited':    m.edited,
            'deleted':   m.deleted,
        })
    emit('chat_history', {'history': history, 'other_id': other_id})

@socketio.on('private_message')
def handle_private_message(data):
    receiver_id = int(data['receiver_id'])
    content     = data['content'].strip()
    if not content:
        return

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        return

    msg = PrivateMessage(sender_id=current_user.id, receiver_id=receiver_id, content=content)
    db.session.add(msg)
    db.session.commit()

    room = private_room(current_user.id, receiver_id)
    emit('new_message', {
        'id':          msg.id,
        'sender_id':   current_user.id,
        'sender':      current_user.username,
        'receiver_id': receiver_id,
        'content':     content,
        'timestamp':   msg.timestamp.strftime('%H:%M'),
        'edited':      False,
        'deleted':     False,
    }, room=room)



@socketio.on("typing")
def handle_typing(data):

    receiver_id = int(data["receiver_id"])

    room = private_room(current_user.id, receiver_id)

    emit(
        "user_typing",
        {
            "user_id": current_user.id,
            "username": current_user.username
        },
        room=room,
        include_self=False
    )


@socketio.on("stop_typing")
def handle_stop_typing(data):

    receiver_id = int(data["receiver_id"])

    room = private_room(current_user.id, receiver_id)

    emit(
        "user_stop_typing",
        {
            "user_id": current_user.id
        },
        room=room,
        include_self=False
    )

@socketio.on('edit_message')
def handle_edit_message(data):
    msg_id  = int(data['msg_id'])
    content = data['content'].strip()
    if not content:
        return

    msg = db.session.get(PrivateMessage, msg_id)
    if not msg or msg.sender_id != current_user.id or msg.deleted:
        return

    msg.content = content
    msg.edited  = True
    db.session.commit()

    room = private_room(msg.sender_id, msg.receiver_id)
    emit('message_edited', {
        'msg_id':  msg_id,
        'content': content,
    }, room=room)

@socketio.on('delete_message')
def handle_delete_message(data):
    msg_id = int(data['msg_id'])
    msg = db.session.get(PrivateMessage, msg_id)
    if not msg or msg.sender_id != current_user.id:
        return

    msg.deleted = True
    db.session.commit()

    room = private_room(msg.sender_id, msg.receiver_id)
    emit('message_deleted', {'msg_id': msg_id}, room=room)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template("home.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        hashed = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user   = User(username=form.username.data, email=form.email.data, password=hashed)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('chat'))
        flash('Invalid email or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/chat')
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
    return render_template("chat.html", users=users)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="127.0.0.1", port=5001)
