from flask import Flask, render_template, request, redirect, url_for, flash,session,jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = '123'  # Use a secure key for production

# MongoDB setup for books
client = MongoClient('mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.3.1')
db=client["food_tracking_app"]
menu_collection=db["menu"]
users_collection=db["users"]
cart_collection = db["cart"]  # Collection for storing cart items

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route('/')
def index():
    
    menu_items = list(menu_collection.find())
    username = session.get('username')
    return render_template("index.html", menu_items=menu_items,username=username)
    
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    user = users_collection.find_one({"username": session['username']})
    if not user or user.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    menu_items = list(menu_collection.find())
    return render_template('admin.html', menu_items=menu_items)


@app.route('/update_menu', methods=['GET', 'POST'])
def update_menu():
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    user = users_collection.find_one({"username": session['username']})
    if not user or user.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        item_id = request.form.get('item_id')

        if action == "update":
            quantity = int(request.form.get('quantity', 0))
            menu_collection.update_one({"_id": int(item_id)}, {"$set": {"quantity": quantity}})
            flash('Item quantity updated!', 'success')

        elif action == "delete":
            menu_collection.delete_one({"_id": int(item_id)})
            flash('Item deleted!', 'danger')

        elif action == "add":
            name = request.form.get('name')
            description = request.form.get('description')
            price = float(request.form.get('price'))
            quantity = int(request.form.get('quantity'))

            # Auto-increment `_id`
            last_item = menu_collection.find_one(sort=[("_id", -1)])  # Get the last inserted item
            new_id = (last_item["_id"] + 1) if last_item else 1  # Increment `_id`

            # Handle image upload or URL
            image_url = request.form.get('image_url')  # Get image URL from form
            if 'image_file' in request.files:
                file = request.files['image_file']
                if file.filename:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    image_url = f'static/uploads/{filename}'  # Overwrite URL if file uploaded

            new_item = {
                "_id": new_id,
                "name": name,
                "description": description,
                "price": price,
                "quantity": quantity,
                "image_url": image_url or "static/default.png"  # Use default if nothing is provided
            }
            menu_collection.insert_one(new_item)
            flash('New item added!', 'success')

        return redirect(url_for('update_menu'))

    # Fetch menu items
    menu_items = list(menu_collection.find())
    return render_template('update_menu.html', menu_items=menu_items)

# 🚀 Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find user in database
        user = users_collection.find_one({"email": email, "password": password})

        if user:
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('No account with these details. Please try again.', 'danger')

    return render_template('login.html')


# 🚀 Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        existing_user = users_collection.find_one({"email": email})
        
        if existing_user:
            flash('Account with this email already exists. Try logging in.', 'warning')
            return redirect(url_for('login'))

        # Insert new user
        users_collection.insert_one({
            "username": username,
            "email": email,
            "password": password
        })

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)  # ✅ Remove username from session
    return redirect(url_for('index'))


@app.route('/cart')
def cart():
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    # Fetch user details
    user = users_collection.find_one({"username": session['username']})
    if not user:
        flash('User not found. Please log in again.', 'danger')
        session.pop('username', None)
        return redirect(url_for('login'))

    user_id = str(user['_id'])  

    # Retrieve cart items and fetch item names
    cart_items = list(cart_collection.find({"user_id": user_id}))

    for item in cart_items:
        menu_item = menu_collection.find_one({"_id": int(item['item_id'])})  # Fetch item details
        if menu_item:
            item['name'] = menu_item['name']  # Add item name

    return render_template('cart.html', cart_items=cart_items)

@app.route('/add-to-cart/<item_id>', methods=['POST'])
def add_to_cart(item_id):
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    user = users_collection.find_one({"username": session['username']})
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))

    user_id = str(user['_id'])  # Convert ObjectId to string
    quantity = int(request.form.get('quantity', 1))

    # Fetch menu item details from menu_collection
    menu_item = menu_collection.find_one({"_id": int(item_id)})  # Convert item_id to int
    if not menu_item:
        flash('Item not found!', 'danger')
        return redirect(url_for('index'))
    
    if menu_item.get('quantity', 0) < quantity:
        flash('This item is out of stock!', 'danger')
        return redirect(url_for('index'))

    image_url = menu_item['image_url']
    price = menu_item['price']

    # Check if item is already in the cart
    existing_item = cart_collection.find_one({"user_id": user_id, "item_id": item_id})

    if existing_item:
        # Update quantity in cart
        cart_collection.update_one(
            {"_id": existing_item['_id']}, 
            {"$set": {"quantity": quantity, "price": price, "image_url": image_url}}
        )
        flash('Cart updated successfully!', 'success')
    else:
        # Insert new cart item
        cart_collection.insert_one({
            "user_id": user_id, 
            "item_id": item_id, 
            "image_url": image_url, 
            "price": price, 
            "quantity": quantity
        })
        flash('Item added to cart!', 'success')

    return redirect(url_for('cart'))

@app.route('/update_cart/<item_id>', methods=['POST'])
def update_cart(item_id):
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    user = users_collection.find_one({"username": session['username']})
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))

    user_id = str(user['_id'])
    quantity = int(request.form.get('quantity', 1))

    cart_collection.update_one(
        {"user_id": user_id, "item_id": item_id},
        {"$set": {"quantity": quantity}}
    )

    flash('Cart updated successfully!', 'success')
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<item_id>', methods=['POST'])
def remove_from_cart(item_id):
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    user = users_collection.find_one({"username": session['username']})
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))

    user_id = str(user['_id'])
    cart_collection.delete_one({"user_id": user_id, "item_id": item_id})

    flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))


if __name__ == '__main__':
    app.run(debug=True)