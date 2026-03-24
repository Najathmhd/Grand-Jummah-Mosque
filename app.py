from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify, Response
import sqlite3
import os
import qrcode
import io
import csv
from functools import wraps

app = Flask(__name__)
app.secret_key = 'super_secret_key_masjid_system'
DATABASE = 'masjid.db'
QR_DIR = os.path.join('static', 'qrcodes')
os.makedirs(QR_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        admin = conn.execute('SELECT * FROM admins WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    total_members = conn.execute('SELECT COUNT(*) FROM members').fetchone()[0]
    total_events = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    active_events = conn.execute('SELECT * FROM events ORDER BY id DESC LIMIT 5').fetchall()
    conn.close()
    return render_template('dashboard.html', total_members=total_members, total_events=total_events, events=active_events)

# MEMBER MANAGEMENT
@app.route('/members', methods=['GET', 'POST'])
@login_required
def members():
    conn = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']
        
        # Determine prefix based on area
        prefix_map = {
            'Masjid Mawatha': 'MM',
            'Pilanduwa': 'PL',
            'Town': 'TN'
        }
        prefix = prefix_map.get(area, 'XX')
        
        # Generate ID (Find latest in this area)
        cursor = conn.cursor()
        cursor.execute("SELECT member_id FROM members WHERE area = ? ORDER BY id DESC LIMIT 1", (area,))
        last_member = cursor.fetchone()
        
        if last_member:
            last_id_num = int(last_member['member_id'].split('-')[1])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_member_id = f"{prefix}-{new_id_num:03d}"
        
        try:
            conn.execute("INSERT INTO members (name, phone, area, member_id) VALUES (?, ?, ?, ?)", (name, phone, area, new_member_id))
            conn.commit()
            
            # Generate QR Code implicitly here: QR encodes the member_id directly or a URL
            qr_data = url_for('view_member', member_id=new_member_id, _external=True)
            img = qrcode.make(qr_data)
            qr_path = os.path.join(QR_DIR, f"{new_member_id}.png")
            img.save(qr_path)
            
            flash(f"Member added successfully! ID: {new_member_id}", 'success')
        except sqlite3.IntegrityError:
            flash("Error creating member.", 'error')
            
        return redirect(url_for('members'))
        
    members_list = conn.execute('SELECT * FROM members ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('members.html', members=members_list)

@app.route('/member/card/<member_id>')
def member_card(member_id):
    conn = get_db()
    member = conn.execute('SELECT * FROM members WHERE member_id = ?', (member_id,)).fetchone()
    conn.close()
    if member:
        return render_template('member_card.html', member=member)
    return "Member not found", 404

@app.route('/member/view/<member_id>')
def view_member(member_id):
    conn = get_db()
    member = conn.execute('SELECT * FROM members WHERE member_id = ?', (member_id,)).fetchone()
    conn.close()
    if member:
        return render_template('view_member.html', member=member)
    return "Member not found", 404

@app.route('/member/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    conn = get_db()
    member = conn.execute('SELECT * FROM members WHERE id = ?', (id,)).fetchone()
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']
        conn.execute('UPDATE members SET name = ?, phone = ?, area = ? WHERE id = ?', (name, phone, area, id))
        conn.commit()
        conn.close()
        flash('Member updated successfully!', 'success')
        return redirect(url_for('members'))
    conn.close()
    if not member:
        return "Member not found", 404
    return render_template('edit_member.html', member=member)

@app.route('/member/delete/<int:id>', methods=['POST'])
@login_required
def delete_member(id):
    conn = get_db()
    member = conn.execute('SELECT member_id FROM members WHERE id = ?', (id,)).fetchone()
    if member:
        member_id = member['member_id']
        conn.execute('DELETE FROM distributions WHERE member_id = ?', (member_id,))
        conn.execute('DELETE FROM members WHERE id = ?', (id,))
        conn.commit()
        
        qr_path = os.path.join(QR_DIR, f"{member_id}.png")
        if os.path.exists(qr_path):
            try:
                os.remove(qr_path)
            except Exception as e:
                print(f"Error deleting QR code: {e}")
                
        flash('Member deleted successfully!', 'success')
    conn.close()
    return redirect(url_for('members'))

# DISTRIBUTION EVENT SYSTEM
@app.route('/events', methods=['GET', 'POST'])
@login_required
def events():
    conn = get_db()
    if request.method == 'POST':
        event_name = request.form['event_name']
        item_name = request.form['item_name']
        total_qty = int(request.form['total_quantity'])
        
        conn.execute("INSERT INTO events (event_name, item_name, total_quantity, remaining_quantity) VALUES (?, ?, ?, ?)",
                     (event_name, item_name, total_qty, total_qty))
        conn.commit()
        flash("Event created successfully!", 'success')
        return redirect(url_for('events'))
        
    events_list = conn.execute('SELECT * FROM events ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('events.html', events=events_list)

@app.route('/event/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    conn = get_db()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (id,)).fetchone()
    if request.method == 'POST':
        event_name = request.form['event_name']
        item_name = request.form['item_name']
        total_qty = int(request.form['total_quantity'])
        conn.execute('UPDATE events SET event_name = ?, item_name = ?, total_quantity = ?, remaining_quantity = ? WHERE id = ?', 
                     (event_name, item_name, total_qty, total_qty, id))
        conn.commit()
        conn.close()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))
    conn.close()
    if not event:
        return "Event not found", 404
    return render_template('edit_event.html', event=event)

@app.route('/event/delete/<int:id>', methods=['POST'])
@login_required
def delete_event(id):
    conn = get_db()
    conn.execute('DELETE FROM distributions WHERE event_id = ?', (id,))
    conn.execute('DELETE FROM events WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))

@app.route('/distribution/<int:event_id>')
@login_required
def live_distribution(event_id):
    conn = get_db()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    conn.close()
    if not event:
        return "Event not found", 404
    return render_template('distribution.html', event=event)

@app.route('/api/scan', methods=['POST'])
@login_required
def api_scan():
    data = request.json
    event_id = data.get('event_id')
    qr_content = data.get('qr_content')
    
    # Extract member ID, assuming qr_content is a URL or just member_id
    member_id = qr_content
    if '/member/view/' in qr_content:
        member_id = qr_content.split('/member/view/')[1]
        
    conn = get_db()
    member = conn.execute('SELECT * FROM members WHERE member_id = ?', (member_id,)).fetchone()
    
    if not member:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Unknown Member ID'}), 404
        
    # Check if already received
    dist = conn.execute('SELECT * FROM distributions WHERE event_id = ? AND member_id = ?', (event_id, member_id)).fetchone()
    
    if dist:
        conn.close()
        return jsonify({
            'status': 'error', 
            'message': 'Already Received', 
            'member': dict(member)
        }), 400
        
    # Fetch event to check stock
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    if event['remaining_quantity'] <= 0:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Out of Stock'}), 400
        
    conn.close()
    return jsonify({
        'status': 'success',
        'message': 'Member verified, ready to give item',
        'member': dict(member)
    })

@app.route('/api/give', methods=['POST'])
@login_required
def api_give():
    data = request.json
    event_id = data.get('event_id')
    member_id = data.get('member_id')
    
    conn = get_db()
    
    # Double check stock
    event = conn.execute('SELECT remaining_quantity FROM events WHERE id = ?', (event_id,)).fetchone()
    if not event or event['remaining_quantity'] <= 0:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Out of Stock'}), 400
        
    try:
        conn.execute('INSERT INTO distributions (event_id, member_id) VALUES (?, ?)', (event_id, member_id))
        conn.execute('UPDATE events SET remaining_quantity = remaining_quantity - 1 WHERE id = ?', (event_id,))
        conn.commit()
        
        # Get updated count
        updated_event = conn.execute('SELECT remaining_quantity FROM events WHERE id = ?', (event_id,)).fetchone()
        conn.close()
        return jsonify({
            'status': 'success',
            'message': 'Item marked as given!',
            'remaining_quantity': updated_event['remaining_quantity']
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Already Received (Duplicate Error)'}), 400

@app.route('/export/event/<int:event_id>')
@login_required
def export_csv(event_id):
    conn = get_db()
    event = conn.execute('SELECT event_name FROM events WHERE id = ?', (event_id,)).fetchone()
    if not event:
        conn.close()
        return "Event not found", 404
        
    distributions = conn.execute('''
        SELECT d.timestamp, m.member_id, m.name, m.area, m.phone 
        FROM distributions d
        JOIN members m ON d.member_id = m.member_id
        WHERE d.event_id = ?
        ORDER BY d.timestamp DESC
    ''', (event_id,)).fetchall()
    conn.close()
    
    def generate():
        yield 'Timestamp,Member ID,Name,Area,Phone\n'
        for row in distributions:
            yield f"{row['timestamp']},{row['member_id']},{row['name']},{row['area']},{row['phone']}\n"
            
    return Response(generate(), mimetype='text/csv', 
                    headers={'Content-Disposition': f'attachment; filename=event_{event_id}_distribution.csv'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
