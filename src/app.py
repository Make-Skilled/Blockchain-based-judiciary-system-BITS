from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from bson import ObjectId
from werkzeug.utils import secure_filename
from contract_config import contract_config
from functools import wraps
from flask_socketio import SocketIO, emit, join_room, leave_room

# Use the singleton instance
if not contract_config.initialized:
    raise Exception("Failed to initialize Web3 and Contract. Please check Ganache connection.")

# Get the instances from the config
w3 = contract_config.w3
contract = contract_config.contract
GANACHE_ADDRESS = contract_config.ganache_address

app = Flask(__name__, 
    static_folder='static',  # This points to src/static
    template_folder='templates'  # This points to src/templates
)
app.secret_key = 'your-secret-key'

# File upload configuration
UPLOAD_FOLDER = os.path.join('src', 'static', 'certificates')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create certificates directory if it doesn't exist
certificates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'certificates')
os.makedirs(certificates_path, exist_ok=True)

# Global variables for Web3 and Contract
ADMIN_ADDRESS = None
CONTRACT_ADDRESS = None

# At the top of your file, add these constants
PRIVATE_KEY = "your_private_key_here"  # Your Ganache private key for this address

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MongoDB connection with error handling
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['judiciary']
    # Test the connection
    client.server_info()
    print("MongoDB connection successful!")
except Exception as e:
    print(f"MongoDB connection error: {e}")

# Create default admin if not exists
default_admin = {
    'username': 'admin',
    'password': generate_password_hash('admin123')  # Change this password
}

if not db.admins.find_one({'username': 'admin'}):
    db.admins.insert_one(default_admin)
    print("Default admin account created")

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Routes for pages
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering index: {e}")
        return str(e), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    user_type = request.form.get('user_type')
    
    if user_type == 'lawyer':
        return redirect(url_for('lawyer_login'))
    elif user_type == 'client':
        return redirect(url_for('client_login'))
    else:
        return "Invalid user type", 400

@app.route('/register/client', methods=['GET', 'POST'])
def client_register():
    if request.method == 'GET':
        return render_template('client_register.html')
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Check if client already exists
            if db.clients.find_one({'email': email}):
                return render_template('client_register.html', 
                                    error="Email already registered")
            
            # Create new client
            new_client = {
                'name': name,
                'email': email,
                'password': generate_password_hash(password),
                'created_at': datetime.utcnow()
            }
            
            db.clients.insert_one(new_client)
            return redirect(url_for('client_login'))
            
        except Exception as e:
            print(f"Error in client registration: {e}")
            return render_template('client_register.html', 
                                error="Registration failed")

@app.route('/register/lawyer', methods=['GET', 'POST'])
def lawyer_register():
    if request.method == 'GET':
        return render_template('lawyer_register.html')
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            mobile = request.form.get('mobile')
            password = request.form.get('password')
            specialization = request.form.get('specialization')
            experience = request.form.get('experience')
            court_type = request.form.get('court_type')
            
            print(f"Processing registration for {name}")
            
            # Check if email already exists
            if db.lawyers.find_one({'email': email}):
                return "Email already registered", 400
            
            # Handle certificate upload
            if 'certificate' not in request.files:
                return "No certificate file uploaded", 400
                
            file = request.files['certificate']
            if file.filename == '':
                return "No selected file", 400
                
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                relative_filepath = f"certificates/{unique_filename}"
                full_filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                
                # Save the file
                file.save(full_filepath)
                print(f"Certificate saved: {relative_filepath}")
                
                try:
                    print("Initiating blockchain transaction...")
                    print(f"Using Ganache address: {GANACHE_ADDRESS}")
                    
                    # Register on blockchain
                    tx_hash = contract.functions.registerLawyer(
                        name,
                        email,
                        mobile,
                        relative_filepath,
                        specialization,
                        str(experience),
                        court_type
                    ).transact({
                        'from': GANACHE_ADDRESS,
                        'gas': 2000000,
                        'gasPrice': w3.eth.gas_price
                    })
                    
                    print(f"Transaction hash: {tx_hash.hex()}")
                    
                    # Wait for transaction receipt
                    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                    print(f"Transaction mined in block: {tx_receipt['blockNumber']}")
                    print(f"Gas used: {tx_receipt['gasUsed']}")
                    
                    # Store in MongoDB
                    new_lawyer = {
                        'name': name,
                        'email': email,
                        'mobile': mobile,
                        'password': generate_password_hash(password),
                        'specialization': specialization,
                        'experience': experience,
                        'court_type': court_type,
                        'certificate_path': relative_filepath,
                        'status': 'pending',
                        'transaction_hash': tx_hash.hex(),
                        'blockchain_address': GANACHE_ADDRESS,
                        'created_at': datetime.utcnow()
                    }
                    
                    result = db.lawyers.insert_one(new_lawyer)
                    print(f"MongoDB document created with ID: {result.inserted_id}")
                    
                    return redirect(url_for('lawyer_login'))
                    
                except Exception as e:
                    print(f"Blockchain error: {e}")
                    if os.path.exists(full_filepath):
                        os.remove(full_filepath)
                    return f"Blockchain error: {str(e)}", 500
                
        except Exception as e:
            print(f"Registration error: {e}")
            return str(e), 500

    return render_template('lawyer_register.html')

@app.route('/client/dashboard')
def client_dashboard():
    try:
        if 'client_id' not in session:
            return redirect(url_for('client_login'))
        
        client_id = ObjectId(session['client_id'])
        client = db.clients.find_one({'_id': client_id})
        
        if not client:
            session.clear()
            return redirect(url_for('client_login'))
        
        # Get approved lawyers
        approved_lawyers = list(db.lawyers.find({'status': 'approved'}))
        
        # Get client's cases
        my_cases = list(db.cases.find({'client_id': client_id}))
        
        # Get client's meeting requests with lawyer information
        meeting_requests = list(db.meetings.find({'client_id': client_id}))
        for request in meeting_requests:
            lawyer = db.lawyers.find_one({'_id': request['lawyer_id']})
            request['lawyer_name'] = lawyer['name'] if lawyer else 'Unknown Lawyer'
        
        return render_template('client_dashboard.html',
                             client=client,
                             approved_lawyers=approved_lawyers,
                             my_cases=my_cases,
                             meeting_requests=meeting_requests)
    except Exception as e:
        print(f"Error in client dashboard: {e}")
        return redirect(url_for('client_login'))

@app.route('/lawyer/login', methods=['GET', 'POST'])
def lawyer_login():
    if request.method == 'GET':
        return render_template('lawyer_login.html')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        lawyer = db.lawyers.find_one({'email': email})
        
        if lawyer and check_password_hash(lawyer['password'], password):
            if lawyer['status'] == 'approved':
                session['lawyer_id'] = str(lawyer['_id'])
                session['user_type'] = 'lawyer'
                return redirect(url_for('lawyer_dashboard'))
            else:
                return render_template('lawyer_login.html', 
                                    error="Your account is pending approval")
        
        return render_template('lawyer_login.html', 
                            error="Invalid email or password")

@app.route('/lawyer/logout')
def lawyer_logout():
    session.pop('lawyer_id', None)
    session.pop('lawyer_email', None)
    return redirect(url_for('index'))

@app.route('/lawyer/dashboard')
def lawyer_dashboard():
    if 'lawyer_id' not in session:
        return redirect(url_for('lawyer_login'))

    lawyer_id = ObjectId(session['lawyer_id'])
    lawyer = db.lawyers.find_one({'_id': lawyer_id})
    
    if not lawyer:
        session.clear()
        return redirect(url_for('lawyer_login'))

    try:
        # Get meeting requests with client information
        schedule_requests = list(db.meetings.find({'lawyer_id': lawyer_id}).sort('created_at', -1).limit(5))
        
        # Get client names for each request
        for request in schedule_requests:
            client = db.clients.find_one({'_id': request['client_id']})
            request['client_name'] = client['name'] if client else 'Unknown Client'

        # Get conversations
        conversations = list(db.conversations.find({'lawyer_id': lawyer_id}))
        for conv in conversations:
            client = db.clients.find_one({'_id': conv['client_id']})
            conv['client_name'] = client['name'] if client else 'Unknown Client'
            # Get last message time
            last_message = db.messages.find_one(
                {'conversation_id': conv['_id']},
                sort=[('timestamp', -1)]
            )
            conv['last_message_time'] = last_message['timestamp'] if last_message else None

        # Count statistics
        pending_count = db.meetings.count_documents({
            'lawyer_id': lawyer_id,
            'status': 'pending'
        })
        
        accepted_count = db.meetings.count_documents({
            'lawyer_id': lawyer_id,
            'status': 'accepted'
        })
        
        total_cases = db.cases.count_documents({
            'lawyer_id': lawyer_id
        })

        return render_template('lawyer_dashboard.html',
                             lawyer=lawyer,
                             schedule_requests=schedule_requests,
                             schedule_count=pending_count,
                             accepted_count=accepted_count,
                             total_cases=total_cases,
                             conversations=conversations)
                             
    except Exception as e:
        print(f"Error in lawyer dashboard: {e}")
        return redirect(url_for('lawyer_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Add admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:  # Make sure we use the correct session key
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check admin credentials (replace with your actual admin credentials)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True  # Set the correct session key
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))
    
    try:
        # Fetch all lawyers from MongoDB
        lawyers = list(db.lawyers.find().sort('created_at', -1))
        print(f"Found {len(lawyers)} lawyers")
        
        return render_template('admin_dashboard.html', lawyers=lawyers)
    except Exception as e:
        print(f"Error fetching lawyers: {e}")
        return str(e), 500

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)  # Use the correct session key
    return redirect(url_for('admin_login'))

@app.route('/admin/update_status/<lawyer_id>/<status>')
def update_lawyer_status(lawyer_id, status):  # Add status parameter here
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Get lawyer details
        lawyer = db.lawyers.find_one({'_id': ObjectId(lawyer_id)})
        if not lawyer:
            return jsonify({'error': 'Lawyer not found'}), 404

        # Get transaction hash
        tx_hash = lawyer.get('transaction_hash')
        if not tx_hash:
            return jsonify({'error': 'Transaction hash not found'}), 400

        # Get lawyer's blockchain address from transaction
        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
        lawyer_address = tx_receipt['from']

        # Update blockchain status
        status_code = 1 if status == 'approve' else 2
        update_tx = contract.functions.updateLawyerStatus(
            lawyer_address,
            status_code
        ).transact({
            'from': GANACHE_ADDRESS,
            'gas': 2000000
        })

        # Wait for transaction confirmation
        w3.eth.wait_for_transaction_receipt(update_tx)

        # Update MongoDB status
        db.lawyers.update_one(
            {'_id': ObjectId(lawyer_id)},
            {'$set': {'status': 'approved' if status == 'approve' else 'rejected'}}
        )

        return jsonify({'success': True, 'message': f'Lawyer {status}d successfully'})

    except Exception as e:
        print(f"Error updating status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/certificates/<filename>')
def serve_certificate(filename):
    return send_from_directory(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'certificates'), filename)

@app.route('/client/login', methods=['GET', 'POST'])
def client_login():
    if request.method == 'GET':
        return render_template('client_login.html')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        client = db.clients.find_one({'email': email})
        
        if client and check_password_hash(client['password'], password):
            session['client_id'] = str(client['_id'])
            session['user_type'] = 'client'
            return redirect(url_for('client_dashboard'))
        else:
            return render_template('client_login.html', 
                                error="Invalid email or password")

@app.route('/client/request-lawyer/<lawyer_id>', methods=['POST'])
def request_lawyer(lawyer_id):
    if 'client_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    try:
        # Create new case request
        new_case = {
            'client_id': session['client_id'],
            'lawyer_id': lawyer_id,
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        
        db.cases.insert_one(new_case)
        return jsonify({'success': True, 'message': 'Request sent successfully'})
        
    except Exception as e:
        print(f"Error in requesting lawyer: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Client routes for scheduling
@app.route('/client/lawyer/details/<lawyer_id>')
def get_lawyer_details_for_client(lawyer_id):
    try:
        lawyer = db.lawyers.find_one({'_id': ObjectId(lawyer_id)})
        if lawyer:
            return jsonify({
                'name': lawyer['name'],
                'email': lawyer['email'],
                'mobile': lawyer['mobile'],
                'specialization': lawyer['specialization'],
                'experience': lawyer['experience'],
                'court_type': lawyer['court_type']
            })
        return jsonify({'error': 'Lawyer not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/client/schedule-meet/<lawyer_id>', methods=['GET', 'POST'])
def schedule_meet(lawyer_id):
    if 'client_id' not in session:
        return redirect(url_for('client_login'))

    lawyer = db.lawyers.find_one({'_id': ObjectId(lawyer_id)})
    if not lawyer:
        return "Lawyer not found", 404

    if request.method == 'POST':
        try:
            meeting_date = request.form.get('meeting_date')
            meeting_time = request.form.get('meeting_time')
            purpose = request.form.get('purpose')

            # Combine date and time strings
            meeting_datetime_str = f"{meeting_date} {meeting_time}"
            meeting_datetime = datetime.strptime(meeting_datetime_str, '%Y-%m-%d %H:%M')
            
            # Check if meeting time is in the future
            if meeting_datetime <= datetime.now():
                return render_template('schedule_meet.html', 
                                    error="Please select a future date and time",
                                    lawyer=lawyer)

            # Store in MongoDB
            new_meeting = {
                'lawyer_id': ObjectId(lawyer_id),
                'client_id': ObjectId(session['client_id']),
                'meeting_datetime': meeting_datetime,
                'purpose': purpose,
                'status': 'pending',
                'created_at': datetime.utcnow()
            }
            
            db.meetings.insert_one(new_meeting)
            return redirect(url_for('client_dashboard'))

        except Exception as e:
            print(f"Error scheduling meeting: {e}")
            return render_template('schedule_meet.html', 
                                error="Error scheduling meeting",
                                lawyer=lawyer)

    # GET request
    return render_template('schedule_meet.html', lawyer=lawyer)

def lawyer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'lawyer_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/lawyer/schedules')
def lawyer_schedules():
    if 'lawyer_id' not in session:
        return redirect(url_for('lawyer_login'))
    
    try:
        # Get all meeting requests for the lawyer
        meeting_requests = list(db.meetings.find({
            'lawyer_id': ObjectId(session['lawyer_id'])
        }).sort('created_at', -1))
        
        # Add client information to each request
        for request in meeting_requests:
            client = db.clients.find_one({'_id': request['client_id']})
            request['client_name'] = client['name'] if client else 'Unknown Client'
            # Format datetime for display
            if 'meeting_datetime' in request:
                request['date'] = request['meeting_datetime'].strftime('%B %d, %Y')
                request['time'] = request['meeting_datetime'].strftime('%I:%M %p')
        
        return render_template('lawyer_schedules.html', meeting_requests=meeting_requests)
        
    except Exception as e:
        print(f"Error fetching schedules: {e}")
        return redirect(url_for('lawyer_dashboard'))

@app.route('/lawyer/update-schedule/<request_id>/<status>', methods=['POST'])
@lawyer_required
def update_schedule_status(request_id, status):
    try:
        # Validate status
        if status not in ['accept', 'reject']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400

        # Update the meeting status in MongoDB
        result = db.meetings.update_one(
            {
                '_id': ObjectId(request_id),
                'lawyer_id': ObjectId(session['lawyer_id'])
            },
            {
                '$set': {
                    'status': 'accepted' if status == 'accept' else 'rejected',
                    'updated_at': datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0:
            return jsonify({'success': False, 'error': 'Meeting request not found or unauthorized'}), 404

        return jsonify({
            'success': True,
            'message': f'Meeting request {status}ed successfully'
        })

    except Exception as e:
        print(f"Error updating schedule status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/lawyer/update-mobile', methods=['POST'])
@lawyer_required
def update_lawyer_mobile():
    if 'lawyer_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        current_mobile = data.get('current_mobile')
        new_mobile = data.get('new_mobile')
        
        # Get lawyer details
        lawyer = db.lawyers.find_one({'_id': ObjectId(session['lawyer_id'])})
        
        # Verify current mobile number
        if lawyer['mobile'] != current_mobile:
            return jsonify({
                'success': False,
                'message': 'Current mobile number is incorrect'
            })
        
        # Check if new mobile is already in use
        existing_lawyer = db.lawyers.find_one({
            '_id': {'$ne': ObjectId(session['lawyer_id'])},
            'mobile': new_mobile
        })
        if existing_lawyer:
            return jsonify({
                'success': False,
                'message': 'This mobile number is already registered'
            })
        
        # Update mobile number in MongoDB
        db.lawyers.update_one(
            {'_id': ObjectId(session['lawyer_id'])},
            {'$set': {'mobile': new_mobile}}
        )
        
        # If using blockchain, update there as well
        try:
            # Set default account
            w3.eth.default_account = ADMIN_ADDRESS
            
            # Update in blockchain (if needed)
            # Add your blockchain update logic here
            
        except Exception as e:
            print(f"Blockchain update error: {e}")
            # You might want to handle this differently depending on your requirements
        
        return jsonify({
            'success': True,
            'message': 'Mobile number updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating mobile number: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while updating mobile number'
        }), 500

@app.route('/lawyer/calendar')
@lawyer_required
def lawyer_calendar():
    if 'lawyer_id' not in session:
        return redirect(url_for('lawyer_login'))
    
    try:
        # Get all meetings for the lawyer
        meetings = list(db.meetings.find({
            'lawyer_id': ObjectId(session['lawyer_id'])
        }))
        
        # Format meetings for calendar
        calendar_events = []
        for meeting in meetings:
            client = db.clients.find_one({'_id': meeting['client_id']})
            client_name = client['name'] if client else 'Unknown Client'
            
            # Define color based on status
            color_map = {
                'pending': '#FCD34D',    # Yellow
                'accepted': '#34D399',    # Green
                'rejected': '#EF4444'     # Red
            }
            
            calendar_events.append({
                'id': str(meeting['_id']),
                'title': f"Meeting with {client_name}",
                'start': meeting['meeting_datetime'].isoformat(),
                'end': (meeting['meeting_datetime'] + timedelta(hours=1)).isoformat(),  # Assuming 1-hour meetings
                'backgroundColor': color_map.get(meeting['status'], '#6B7280'),
                'extendedProps': {
                    'status': meeting['status'],
                    'purpose': meeting['purpose'],
                    'clientName': client_name
                }
            })
        
        return render_template('lawyer_calendar.html', 
                             calendar_events=calendar_events)
                             
    except Exception as e:
        print(f"Error fetching calendar data: {e}")
        return redirect(url_for('lawyer_dashboard'))

def create_or_get_conversation(lawyer_id, client_id):
    """Create a new conversation or get existing one between lawyer and client"""
    conversation = db.conversations.find_one({
        'lawyer_id': ObjectId(lawyer_id),
        'client_id': ObjectId(client_id)
    })
    
    if not conversation:
        conversation_id = db.conversations.insert_one({
            'lawyer_id': ObjectId(lawyer_id),
            'client_id': ObjectId(client_id),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }).inserted_id
        conversation = db.conversations.find_one({'_id': conversation_id})
    
    return conversation

@app.route('/start-chat/<user_id>')
def start_chat(user_id):
    if 'user_type' not in session:
        return redirect(url_for('index'))
    
    try:
        if session['user_type'] == 'lawyer':
            conversation = create_or_get_conversation(
                lawyer_id=session['lawyer_id'],
                client_id=user_id
            )
        else:
            conversation = create_or_get_conversation(
                lawyer_id=user_id,
                client_id=session['client_id']
            )
        
        return redirect(url_for('chat_room', conversation_id=str(conversation['_id'])))
    
    except Exception as e:
        print(f"Error starting chat: {e}")
        return str(e), 500

@app.route('/chat/<conversation_id>')
def chat_room(conversation_id):
    if 'user_type' not in session:
        return redirect(url_for('index'))
    
    try:
        # Get conversation details
        conversation = db.conversations.find_one({'_id': ObjectId(conversation_id)})
        if not conversation:
            return "Conversation not found", 404

        # Verify user has access to this conversation
        user_id = ObjectId(session.get('lawyer_id') or session.get('client_id'))
        if user_id not in [conversation['lawyer_id'], conversation['client_id']]:
            return "Unauthorized", 403

        # Get other participant's details
        other_user_id = conversation['lawyer_id'] if session.get('client_id') else conversation['client_id']
        other_user = None
        if session.get('client_id'):
            other_user = db.lawyers.find_one({'_id': other_user_id})
        else:
            other_user = db.clients.find_one({'_id': other_user_id})

        # Get previous messages
        messages = list(db.messages.find({
            'conversation_id': ObjectId(conversation_id)
        }).sort('timestamp', 1))

        return render_template('chat_room.html',
                             conversation=conversation,
                             other_user=other_user,
                             messages=messages)

    except Exception as e:
        print(f"Error accessing chat room: {e}")
        return str(e), 500

@socketio.on('join')
def on_join(data):
    room = data['conversation_id']
    join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = data['conversation_id']
    leave_room(room)

@socketio.on('send_message')
def handle_message(data):
    try:
        conversation_id = ObjectId(data['conversation_id'])
        content = data['message']
        sender_id = ObjectId(session.get('lawyer_id') or session.get('client_id'))
        sender_type = session.get('user_type')

        # Save message to database
        message = {
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'sender_type': sender_type,
            'content': content,
            'timestamp': datetime.utcnow()
        }
        
        result = db.messages.insert_one(message)
        
        # Emit message to room
        emit('new_message', {
            'message_id': str(result.inserted_id),
            'sender_id': str(sender_id),
            'sender_type': sender_type,
            'content': content,
            'timestamp': message['timestamp'].isoformat()
        }, room=str(conversation_id))

    except Exception as e:
        print(f"Error handling message: {e}")
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    # Initialize Web3 and Contract before starting the app
    if w3 and contract:
        print("Web3 and Contract initialized successfully!")
        print(f"Using Ganache address: {GANACHE_ADDRESS}")
        print(f"Contract address: {contract.address}")
        socketio.run(app, debug=True)
    else:
        print("Failed to initialize Web3 and Contract")
