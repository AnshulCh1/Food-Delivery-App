from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api
from models import db, FoodItem, CartItem, Order, User
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app and database
app = Flask(__name__)
api = Api(app)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.before_request
def create_tables():
    if not hasattr(app, 'db_initialized'):
        db.create_all()
        if not FoodItem.query.first():
            items = [
                FoodItem(name='Pizza', price=10.99),
                FoodItem(name='Burger', price=6.99),
                FoodItem(name='Pasta', price=8.49)
            ]
            db.session.add_all(items)
            db.session.commit()
        app.db_initialized = True



# Cart route
@app.route('/cart')
def cart():
    return render_template('cart.html')

#Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'customer')

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            flash('Username or Email already taken!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash(f'{role.capitalize()} account created successfully!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = user.role
            flash(f'Logged in as {username}!', 'success')
            return redirect(url_for('admin' if user.role == 'admin' else 'home'))
        
        flash('Invalid username or password', 'danger')
        return redirect(url_for('login'))
    
    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

# Home Route (For customers and guests)
@app.route('/')
def home():
    return render_template('index.html')

# Admin Route (Only accessible by admins)
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('home'))

    users = User.query.all()
    menu = FoodItem.query.all()
    return render_template('admin_dashboard.html', users=users, menu=menu)

# add items in menue route
@app.route('/admin/add-item', methods=['POST'])
def add_menu_item():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    name = request.form['name']
    price = request.form['price']

    if not name or not price:
        flash('All fields are required', 'warning')
        return redirect(url_for('admin'))

    try:
        price = float(price)
        new_item = FoodItem(name=name, price=price)
        db.session.add(new_item)
        db.session.commit()
        flash('Food item added successfully!', 'success')
    except ValueError:
        flash('Invalid price entered!', 'danger')

    return redirect(url_for('admin'))

# Update form route for customer 
@app.route('/update-profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.mobile_number = request.form['mobile_number']
        user.address = request.form['address']
        
        # Ensure mobile and address are filled
        if not user.mobile_number or not user.address:
            flash('Both mobile number and address are required!', 'danger')
            return redirect(url_for('update_profile'))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('home'))  # Or redirect to a page that shows order button

    return render_template('update_profile.html', user=user)



class MenuAPI(Resource):
    def get(self):
        menu = FoodItem.query.all()
        return jsonify([{'id': i.id, 'name': i.name, 'price': i.price} for i in menu])

class CartAddAPI(Resource):
    def post(self):
        data = request.json
        item = CartItem.query.filter_by(food_id=data['food_id']).first()
        if item:
            item.quantity += 1
        else:
            item = CartItem(food_id=data['food_id'], quantity=1)
            db.session.add(item)
        db.session.commit()
        return {'message': 'Item added to cart'}

class CartViewAPI(Resource):
    def get(self):
        cart = CartItem.query.all()
        result = []
        for item in cart:
            food = FoodItem.query.get(item.food_id)
            result.append({'name': food.name, 'price': food.price, 'quantity': item.quantity})
        return jsonify(result)

class CheckoutAPI(Resource):
    def post(self):
        cart = CartItem.query.all()
        total = sum(FoodItem.query.get(i.food_id).price * i.quantity for i in cart)
        items = ','.join([str(i.food_id) for i in cart])
        new_order = Order(items=items, total_price=total)
        db.session.add(new_order)
        CartItem.query.delete()
        db.session.commit()
        return {'message': 'Order placed', 'total': total}


api.add_resource(MenuAPI, '/api/menu')
api.add_resource(CartAddAPI, '/api/cart/add')
api.add_resource(CartViewAPI, '/api/cart/view')
api.add_resource(CheckoutAPI, '/api/order/checkout')

if __name__ == '__main__':
    app.run(debug=True)