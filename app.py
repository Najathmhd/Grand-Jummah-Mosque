from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import os
import qrcode
import io
import csv
from functools import wraps
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Supabase Setup
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# For Vercel, we don't use a local storage for QRs. 
# We'll serve them via a route instead.

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
        
        # Check against Supabase admins table
        response = supabase.table('admins').select("*").eq("username", username).eq("password", password).execute()
        
        if response.data:
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
    # Fetch counts
    members_count = supabase.table('members').select("id", count="exact").execute().count
    events_count = supabase.table('events').select("id", count="exact").execute().count
    
    # Recent events
    recent_events = supabase.table('events').select("*").order("created_at", desc=True).limit(5).execute()
    
    return render_template('dashboard.html', 
                           total_members=members_count, 
                           total_events=events_count, 
                           events=recent_events.data)

# MEMBER MANAGEMENT
@app.route('/members', methods=['GET', 'POST'])
@login_required
def members():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']
        
        prefix_map = {
            'Masjid Mawatha': 'MM',
            'Pilanduwa': 'PL',
            'Town': 'TN'
        }
        prefix = prefix_map.get(area, 'XX')
        
        # Determine next Member ID
        last_member = supabase.table('members').select("member_id").eq("area", area).order("id", desc=True).limit(1).execute()
        
        if last_member.data:
            last_id_num = int(last_member.data[0]['member_id'].split('-')[1])
            new_id_num = last_id_num + 1
        else:
            new_id_num = 1
            
        new_member_id = f"{prefix}-{new_id_num:03d}"
        
        try:
            supabase.table('members').insert({
                "name": name, 
                "phone": phone, 
                "area": area, 
                "member_id": new_member_id
            }).execute()
            
            flash(f"Member added successfully! ID: {new_member_id}", 'success')
        except Exception as e:
            flash(f"Error creating member: {str(e)}", 'error')
            
        return redirect(url_for('members'))
        
    members_list = supabase.table('members').select("*").order("created_at", desc=True).execute()
    return render_template('members.html', members=members_list.data)

@app.route('/member/card/<member_id>')
def member_card(member_id):
    member = supabase.table('members').select("*").eq("member_id", member_id).single().execute()
    if member.data:
        return render_template('member_card.html', member=member.data)
    return "Member not found", 404

@app.route('/member/view/<member_id>')
def view_member(member_id):
    member = supabase.table('members').select("*").eq("member_id", member_id).single().execute()
    if member.data:
        return render_template('view_member.html', member=member.data)
    return "Member not found", 404

@app.route('/member/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    member_resp = supabase.table('members').select("*").eq("id", id).single().execute()
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']
        
        supabase.table('members').update({
            "name": name, 
            "phone": phone, 
            "area": area
        }).eq("id", id).execute()
        
        flash('Member updated successfully!', 'success')
        return redirect(url_for('members'))
    
    if not member_resp.data:
        return "Member not found", 404
    return render_template('edit_member.html', member=member_resp.data)

@app.route('/member/delete/<int:id>', methods=['POST'])
@login_required
def delete_member(id):
    member_resp = supabase.table('members').select("member_id").eq("id", id).single().execute()
    if member_resp.data:
        member_id = member_resp.data['member_id']
        
        # Delete distributions then member
        supabase.table('distributions').delete().eq("member_id", member_id).execute()
        supabase.table('members').delete().eq("id", id).execute()
        
        # Remove QR file
        qr_path = os.path.join(QR_DIR, f"{member_id}.png")
        if os.path.exists(qr_path):
            try:
                os.remove(qr_path)
            except Exception as e:
                print(f"Error deleting QR code: {e}")
                
        flash('Member deleted successfully!', 'success')
    return redirect(url_for('members'))

# EVENTS & DISTRIBUTIONS
@app.route('/events', methods=['GET', 'POST'])
@login_required
def events():
    if request.method == 'POST':
        event_name = request.form['event_name']
        item_name = request.form['item_name']
        total_qty = int(request.form['total_quantity'])
        
        supabase.table('events').insert({
            "event_name": event_name, 
            "item_name": item_name, 
            "total_quantity": total_qty, 
            "remaining_quantity": total_qty
        }).execute()
        
        flash("Event created successfully!", 'success')
        return redirect(url_for('events'))
        
    events_list = supabase.table('events').select("*").order("created_at", desc=True).execute()
    return render_template('events.html', events=events_list.data)

@app.route('/event/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    event_resp = supabase.table('events').select("*").eq("id", id).single().execute()
    if request.method == 'POST':
        event_name = request.form['event_name']
        item_name = request.form['item_name']
        total_qty = int(request.form['total_quantity'])
        
        supabase.table('events').update({
            "event_name": event_name, 
            "item_name": item_name, 
            "total_quantity": total_qty, 
            "remaining_quantity": total_qty
        }).eq("id", id).execute()
        
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))
        
    if not event_resp.data:
        return "Event not found", 404
    return render_template('edit_event.html', event=event_resp.data)

@app.route('/event/delete/<int:id>', methods=['POST'])
@login_required
def delete_event(id):
    supabase.table('distributions').delete().eq("event_id", id).execute()
    supabase.table('events').delete().eq("id", id).execute()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))

@app.route('/distribution/<int:event_id>')
@login_required
def live_distribution(event_id):
    event_resp = supabase.table('events').select("*").eq("id", event_id).single().execute()
    if not event_resp.data:
        return "Event not found", 404
    return render_template('distribution.html', event=event_resp.data)

@app.route('/api/scan', methods=['POST'])
@login_required
def api_scan():
    data = request.json
    event_id = data.get('event_id')
    qr_content = data.get('qr_content')
    
    member_id = qr_content
    if '/member/view/' in qr_content:
        member_id = qr_content.split('/member/view/')[1]
        
    member_resp = supabase.table('members').select("*").eq("member_id", member_id).single().execute()
    
    if not member_resp.data:
        return jsonify({'status': 'error', 'message': 'Unknown Member ID'}), 404
        
    dist_resp = supabase.table('distributions').select("*").eq("event_id", event_id).eq("member_id", member_id).execute()
    
    if dist_resp.data:
        return jsonify({
            'status': 'error', 
            'message': 'Already Received', 
            'member': member_resp.data
        }), 400
        
    event_resp = supabase.table('events').select("remaining_quantity").eq("id", event_id).single().execute()
    if event_resp.data['remaining_quantity'] <= 0:
        return jsonify({'status': 'error', 'message': 'Out of Stock'}), 400
        
    return jsonify({
        'status': 'success',
        'message': 'Member verified, ready to give item',
        'member': member_resp.data
    })

@app.route('/api/give', methods=['POST'])
@login_required
def api_give():
    data = request.json
    event_id = data.get('event_id')
    member_id = data.get('member_id')
    
    # Check item status again
    event_resp = supabase.table('events').select("remaining_quantity").eq("id", event_id).single().execute()
    if not event_resp.data or event_resp.data['remaining_quantity'] <= 0:
        return jsonify({'status': 'error', 'message': 'Out of Stock'}), 400
        
    try:
        # Transaction-like approach (manual update)
        supabase.table('distributions').insert({
            "event_id": event_id, 
            "member_id": member_id
        }).execute()
        
        # RPC call for decrementing or manual update
        # For simplicity, doing manual decrement
        new_qty = event_resp.data['remaining_quantity'] - 1
        supabase.table('events').update({"remaining_quantity": new_qty}).eq("id", event_id).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Item marked as given!',
            'remaining_quantity': new_qty
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 400

@app.route('/export/event/<int:event_id>')
@login_required
def export_csv(event_id):
    event_resp = supabase.table('events').select("event_name").eq("id", event_id).single().execute()
    if not event_resp.data:
        return "Event not found", 404
        
    # Join manually since Supabase works differently
    dists = supabase.table('distributions').select("timestamp, member_id").eq("event_id", event_id).execute()
    
    def generate():
        yield 'Timestamp,Member ID,Name,Area,Phone\n'
        for d in dists.data:
            m = supabase.table('members').select("*").eq("member_id", d['member_id']).single().execute().data
            if m:
                yield f"{d['timestamp']},{d['member_id']},{m['name']},{m['area']},{m['phone']}\n"
            
    return Response(generate(), mimetype='text/csv', 
                    headers={'Content-Disposition': f'attachment; filename=event_{event_id}_distribution.csv'})

@app.route('/qr/<member_id>')
def serve_qr(member_id):
    qr_data = url_for('view_member', member_id=member_id, _external=True)
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
