from flask import Blueprint, request, jsonify, session, g, render_template, redirect, url_for, flash
from .services import AuthService, TicketService

auth_bp = Blueprint('auth', __name__)
ticket_bp = Blueprint('ticket', __name__)

# --- Auth Routes ---

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not email or not username or not password:
            flash('Missing data', 'danger')
            return render_template('register.html')
            
        user = AuthService.register(email, username, password)
        if user:
            flash('User registered successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('User already exists', 'danger')
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = AuthService.login(email, password)
        if user:
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('ticket.my_tickets'))
        else:
            flash('Invalid credentials', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

# --- Ticket Routes ---

@ticket_bp.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user_id = None
    else:
        g.user_id = user_id

@ticket_bp.route('/', methods=['GET'])
def index():
    if g.user_id:
        return redirect(url_for('ticket.my_tickets'))
    return redirect(url_for('auth.login'))

@ticket_bp.route('/my-tickets', methods=['GET'])
def my_tickets():
    if g.user_id is None:
        flash('Please login to view your tickets', 'warning')
        return redirect(url_for('auth.login'))
        
    tickets = TicketService.get_user_tickets(g.user_id)
    # Pass the enum objects or values to the template if needed, 
    # but simpler to just pass the ticket objects.
    return render_template('my_tickets.html', tickets=tickets)

@ticket_bp.route('/pay-ticket/<int:ticket_id>', methods=['POST'])
def pay_ticket(ticket_id):
    if g.user_id is None:
        return redirect(url_for('auth.login'))
        
    success = TicketService.process_payment(g.user_id, ticket_id)
    if success:
        flash('Payment successful!', 'success')
    else:
        flash('Payment failed or invalid ticket state.', 'danger')
    return redirect(url_for('ticket.my_tickets'))

@ticket_bp.route('/refund-ticket/<int:ticket_id>', methods=['POST'])
def refund_ticket(ticket_id):
    if g.user_id is None:
        return redirect(url_for('auth.login'))
        
    success = TicketService.refund_ticket(g.user_id, ticket_id)
    if success:
        flash('Refund processed successfully.', 'success')
    else:
        flash('Refund failed. Ticket might not be refundable.', 'danger')
    return redirect(url_for('ticket.my_tickets'))

@ticket_bp.route('/use-ticket/<int:ticket_id>', methods=['POST'])
def use_ticket(ticket_id):
    if g.user_id is None:
        return redirect(url_for('auth.login'))
        
    success = TicketService.use_ticket(g.user_id, ticket_id)
    if success:
        flash('Ticket used! Enjoy the event.', 'success')
    else:
        flash('Could not use ticket.', 'danger')
    return redirect(url_for('ticket.my_tickets'))