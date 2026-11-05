"""Inventory Management System Application Layer running on Flask and MySQL."""

import os
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretk8skey')

# Database Configuration (Parameterized for Kubernetes Envs)
DB_HOST = os.environ.get('DB_HOST', 'mysql-service')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')
DB_NAME = os.environ.get('DB_NAME', 'inventory_db')


def get_db_connection():
    """Establish and return a connection to the MySQL database."""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


@app.route('/')
def index():
    """Fetch all active items from the registry and render the dashboard."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM items ORDER BY created_at DESC")
        items = cursor.fetchall()
        cursor.close()
        conn.close()
    except mysql.connector.Error as e:
        items = []
        flash(f"Database connection error: {str(e)}", "danger")

    return render_template('index.html', items=items)


@app.route('/add', methods=['POST'])
def add_item():
    """Process form inputs and add a new item record to the database."""
    sku = request.form.get('sku')
    name = request.form.get('name')
    category = request.form.get('category')
    quantity = request.form.get('quantity', 0)
    price = request.form.get('price', 0.00)

    if not sku or not name or not category:
        flash("Please fill in all required fields.", "warning")
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = (
            "INSERT INTO items (sku, name, category, quantity, price) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        cursor.execute(query, (sku, name, category, quantity, price))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Item '{name}' successfully committed to registry!", "success")
    except mysql.connector.IntegrityError:
        flash(f"Error: SKU Code '{sku}' already exists.", "danger")
    except mysql.connector.Error as e:
        flash(f"An error occurred: {str(e)}", "danger")

    return redirect(url_for('index'))


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    """Remove a specific inventory item by its unique ID record."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Item removed successfully from inventory registry.", "success")
    except mysql.connector.Error as e:
        flash(f"Failed to remove item: {str(e)}", "danger")

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

