from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from fpdf import FPDF

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
    if session['user_role'] == 'supervisor':
        return redirect(url_for('supervisor_entries'))
    else:
        return redirect(url_for('entries'))

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

@app.route('/entries/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM logbook_entries WHERE id = %s AND student_id = %s',
                    (entry_id, session['user_id']))
    entry = cursor.fetchone()

    if not entry:
        conn.close()
        flash("Entry not found or you don't have permission to edit it.")
        return redirect(url_for('entries'))

    if request.method == 'POST':
        entry_date = request.form['entry_date']
        description = request.form['description']
        cursor.execute(
            'UPDATE logbook_entries SET entry_date = %s, description = %s WHERE id = %s',
            (entry_date, description, entry_id)
        )
        conn.commit()
        conn.close()
        flash('Entry updated successfully!')
        return redirect(url_for('entries'))

    conn.close()
    return render_template('edit_entry.html', entry=entry)

@app.route('/entries/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM logbook_entries WHERE id = %s AND student_id = %s',
                    (entry_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Entry deleted.')
    return redirect(url_for('entries'))

@app.route('/entries/report', methods=['GET', 'POST'])
def entry_report():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM logbook_entries WHERE student_id = %s AND entry_date BETWEEN %s AND %s ORDER BY entry_date',
            (session['user_id'], start_date, end_date)
        )
        report_entries = cursor.fetchall()

        cursor.execute('SELECT name FROM users WHERE id = %s', (session['user_id'],))
        student = cursor.fetchone()
        conn.close()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'Logbook Report', ln=True)
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 8, f"Student: {student['name']}", ln=True)
        pdf.cell(0, 8, f"Date range: {start_date} to {end_date}", ln=True)
        pdf.ln(5)

        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(35, 8, 'Date', border=1)
        pdf.cell(115, 8, 'Description', border=1)
        pdf.cell(30, 8, 'Status', border=1, ln=True)

        pdf.set_font('Helvetica', '', 10)
        for entry in report_entries:
            pdf.cell(35, 8, str(entry['entry_date']), border=1)
            pdf.cell(115, 8, entry['description'][:60], border=1)
            pdf.cell(30, 8, entry['status'], border=1, ln=True)

        pdf_bytes = bytes(pdf.output())
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=logbook_report.pdf'}
        )

    return render_template('report_form.html')

@app.route('/supervisor/entries')
def supervisor_entries():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    if session.get('user_role') != 'supervisor':
        flash('Access denied. Supervisors only.')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT logbook_entries.*, users.name AS student_name
        FROM logbook_entries
        JOIN users ON logbook_entries.student_id = users.id
        ORDER BY logbook_entries.entry_date DESC
    ''')
    all_entries = cursor.fetchall()
    conn.close()
    return render_template('supervisor_entries.html', entries=all_entries)


@app.route('/supervisor/entries/<int:entry_id>/approve', methods=['POST'])
def approve_entry(entry_id):
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    if session.get('user_role') != 'supervisor':
        flash('Access denied.')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE logbook_entries SET status = %s WHERE id = %s', ('approved', entry_id))
    conn.commit()
    conn.close()
    flash('Entry approved.')
    return redirect(url_for('supervisor_entries'))


@app.route('/supervisor/entries/<int:entry_id>/reject', methods=['POST'])
def reject_entry(entry_id):
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    if session.get('user_role') != 'supervisor':
        flash('Access denied.')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE logbook_entries SET status = %s WHERE id = %s', ('rejected', entry_id))
    conn.commit()
    conn.close()
    flash('Entry rejected.')
    return redirect(url_for('supervisor_entries'))

if __name__ == '__main__':
    app.run(debug=True)