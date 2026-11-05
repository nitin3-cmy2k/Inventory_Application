import os
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
import mysql.connector
from mysql.connector import Error
from mysql.connector import pooling

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_fallback_key")

# Retrieve environment variables injected by Kubernetes
DB_HOST = os.environ.get("DB_HOST", "mysql-service")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "SecretPassword123")
DB_NAME = os.environ.get("DB_NAME", "inventory_db")

db_pool = None

def init_db():
    """Initializes the schema structure. Safe to call multiple times."""
    for i in range(10):  # Retry loop for slower cluster environments
        try:
            # Added auth_plugin configuration to ensure clean K8s handshakes
            conn = mysql.connector.connect(
                host=DB_HOST, 
                user=DB_USER, 
                password=DB_PASSWORD,
                auth_plugin='mysql_native_password'
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            cursor.execute(f"USE {DB_NAME}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sku VARCHAR(50) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    category VARCHAR(50),
                    quantity INT NOT NULL DEFAULT 0,
                    price DECIMAL(10, 2) NOT NULL,
                    is_hidden TINYINT(1) NOT NULL DEFAULT 0
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
            print("Database schema verified/initialized successfully.")
            return True
        except Error as e:
            print(f"Database connection attempt {i+1} failed. Retrying in 5s... Error: {e}")
            time.sleep(5)
    return False

def get_db_pool():
    """Thread-safe on-demand pool allocator."""
    global db_pool
    if db_pool is None:
        try:
            db_pool = pooling.MySQLConnectionPool(
                pool_name="inventory_pool",
                pool_size=10, 
                pool_reset_session=True,
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                auth_plugin='mysql_native_password'
            )
            print("MySQL connection pool established.")
        except Error as e:
            print(f"Failed to create connection pool: {e}")
    return db_pool

def get_db_connection():
    """Fetches a connection from the pool and attaches it to Flask's request context."""
    if 'db_conn' not in g:
        pool = get_db_pool()
        if pool is None:
            return None
        try:
            g.db_conn = pool.get_connection()
        except Error as e:
            print(f"Pool connection exhaustion or error: {e}")
            return None
    return g.db_conn

@app.teardown_appcontext
def close_db_connection(exception):
    """Guarantees that the connection returns to the pool at the end of every request lifecycle."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        try:
            conn.close()  # Puts connection back in pool
        except Error as e:
            print(f"Error returning connection to pool: {e}")

@app.route('/')
def index():
    conn = get_db_connection()
    if conn is None: 
        return "Database Connection Pool Error", 500
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Table view only displays active stock items that are not explicitly hidden
            cursor.execute("SELECT * FROM inventory WHERE is_hidden = 0")
            items = cursor.fetchall()
            
            # The dropdown maps out all items currently inside the database registry
            cursor.execute("SELECT id, name, sku FROM inventory")
            dropdown_items = cursor.fetchall()
            
        return render_template('index.html', items=items, dropdown_items=dropdown_items)
    except Error as e:
        return f"Database query failed: {e}", 500

@app.route('/item/<int:item_id>', methods=['GET'])
def get_item_details(item_id):
    conn = get_db_connection()
    if conn is None: 
        return jsonify({"error": "Database error"}), 500
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM inventory WHERE id = %s", (item_id,))
            item = cursor.fetchone()
            
        if item is None: 
            return jsonify({"error": "Item not found"}), 404
            
        item['price'] = float(item['price'])
        return jsonify(item), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add', methods=['POST'])
def add_item():
    sku = request.form['sku'].strip()
    name = request.form['name'].strip()
    category = request.form['category'].strip()
    add_qty = int(request.form['quantity'])
    price = float(request.form['price'])
    
    conn = get_db_connection()
    if conn is None:
        flash("Database error: Could not acquire connection.", "danger")
        return redirect(url_for('index'))
        
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Check if an entry with this unique SKU code already exists in the registry
            cursor.execute("SELECT id, quantity FROM inventory WHERE sku = %s", (sku,))
            existing_item = cursor.fetchone()
            
            if existing_item:
                # 1. Calculation: Increase existing count and make sure it is unhidden
                new_quantity = existing_item['quantity'] + add_qty
                cursor.execute(
                    "UPDATE inventory SET quantity = %s, name = %s, category = %s, price = %s, is_hidden = 0 WHERE id = %s",
                    (new_quantity, name, category, price, existing_item['id'])
                )
                flash(f"SKU {sku} already existed. Stock level increased by {add_qty} (Total: {new_quantity}).", "success")
            else:
                # 2. Add as a brand new registry row item if the SKU code is fresh
                cursor.execute(
                    "INSERT INTO inventory (sku, name, category, quantity, price, is_hidden) VALUES (%s, %s, %s, %s, %s, 0)",
                    (sku, name, category, add_qty, price)
                )
                flash("New item committed to database registry successfully!", "success")
                
            conn.commit()
    except Error as e:
        flash(f"Error processing stock addition: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/hide/<int:item_id>', methods=['POST'])
def hide_item(item_id):
    conn = get_db_connection()
    if conn is None:
        flash("Database error: Could not acquire connection.", "danger")
        return redirect(url_for('index'))
        
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE inventory SET is_hidden = 1 WHERE id = %s", (item_id,))
            conn.commit()
        flash("Item visibility changed to Hidden.", "info")
    except Error as e:
        flash(f"Error hiding record: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/unhide/<int:item_id>', methods=['POST'])
def unhide_item(item_id):
    conn = get_db_connection()
    if conn is None:
        flash("Database error: Could not acquire connection.", "danger")
        return redirect(url_for('index'))
        
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE inventory SET is_hidden = 0 WHERE id = %s", (item_id,))
            conn.commit()
        flash("Item restored to active grid display views.", "success")
    except Error as e:
        flash(f"Error unhiding record: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/remove/<int:item_id>', methods=['POST'])
def remove_item(item_id):
    # Retrieve adjustment quantity deduction size from payload if specified, defaults to 1 item unit
    deduct_qty = int(request.form.get('deduct_quantity', 1))
    
    conn = get_db_connection()
    if conn is None:
        flash("Database error: Could not acquire connection.", "danger")
        return redirect(url_for('index'))
        
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch the target item's data values to calculate balance reduction accurately
            cursor.execute("SELECT name, quantity FROM inventory WHERE id = %s", (item_id,))
            item = cursor.fetchone()
            
            if not item:
                flash("Target registry element not found.", "danger")
                return redirect(url_for('index'))
                
            # 2. Calculation: Deduct quantity, ensuring it doesn't drop below zero
            new_quantity = max(0, item['quantity'] - deduct_qty)
            
            if new_quantity == 0:
                # Automate hidden flag status if quantity drops down completely to 0 units
                cursor.execute("UPDATE inventory SET quantity = 0, is_hidden = 1 WHERE id = %s", (item_id,))
                flash(f"Stock for '{item['name']}' dropped to 0. Item has been removed from active view.", "warning")
            else:
                cursor.execute("UPDATE inventory SET quantity = %s WHERE id = %s", (new_quantity, item_id))
                flash(f"Removed {deduct_qty} unit(s) of '{item['name']}'. Remaining stock level: {new_quantity}.", "info")
                
            conn.commit()
    except Error as e:
        flash(f"Deduction process error occurred: {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/delete/<int:item_id>', methods=['POST'])
def hard_delete_item(item_id):

