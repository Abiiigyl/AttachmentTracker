from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from flask import session


app = Flask(__name__)
app.secret_key = '3d576da5f085fbe3803cb1cef756c7f8'  # needed for flash messages & sessions

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='attachment_tracker',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM logbook_entries')
    entries = cursor.fetchall()
    conn.close()
    return f"Found {len(entries)} logbook entries: {entries}"

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)',
                (name, email, hashed_password, role)
            )
            conn.commit()
            flash('Account created successfully! You can now log in.')
            return redirect(url_for('home'))
        except pymysql.err.IntegrityError:
            flash('That email is already registered.')
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    return f"Welcome! You are logged in as {session['user_role']} (user id {session['user_id']})"

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/entries')
def entries():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM logbook_entries WHERE student_id = %s ORDER BY entry_date DESC',
        (session['user_id'],)
    )
    my_entries = cursor.fetchall()
    conn.close()
    return render_template('entries.html', entries=my_entries)


@app.route('/entries/new', methods=['GET', 'POST'])
def new_entry():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        entry_date = request.form['entry_date']
        description = request.form['description']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO logbook_entries (student_id, entry_date, description) VALUES (%s, %s, %s)',
            (session['user_id'], entry_date, description)
        )
        conn.commit()
        conn.close()
        flash('Entry added successfully!')
        return redirect(url_for('entries'))

    return render_template('new_entry.html')

if __name__ == '__main__':
    app.run(debug=True)