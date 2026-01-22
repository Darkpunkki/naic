# auth_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User
from scripts.init_db import db

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not password or not email:
            flash('Username, email, and password are required.', 'error')
            return redirect(url_for('auth_bp.register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'error')
            return redirect(url_for('auth_bp.register'))

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already in use.', 'error')
            return redirect(url_for('auth_bp.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth_bp.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth_bp.login'))

        session['user_id'] = user.user_id
        session['username'] = user.username

        flash('Logged in successfully.', 'success')
        return redirect(url_for('main_bp.index'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_bp.login'))
