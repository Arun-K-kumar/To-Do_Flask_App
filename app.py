import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Vercel-Admin-anonymodb:gT9ms2NvudGoMJIJ@anonymodb.zsfrs5v.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = "todo_app"
COLLECTION_NAME = "todos"

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]


def load_todos():
    """Load todos from MongoDB."""
    return list(collection.find())


def save_todos(todos):
    """Save todos to MongoDB."""
    collection.delete_many({})
    for todo in todos:
        collection.insert_one(todo)


def create_todo(description, priority="medium"):
    """Create a new todo item."""
    todos = load_todos()
    todo_id = len(todos) + 1
    todo = {
        "description": description,
        "priority": priority,
        "completed": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    collection.insert_one(todo)
    return todo


def update_todo(todo_id, description=None, priority=None, completed=None):
    """Update an existing todo item."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if str(todo.get("_id", "")) == str(todo_id):
            if description is not None:
                todos[i]["description"] = description
            if priority is not None:
                todos[i]["priority"] = priority
            if completed is not None:
                todos[i]["completed"] = completed
            save_todos(todos)
            return todos[i]
    
    return None


def delete_todo(todo_id):
    """Delete a todo item."""
    result = collection.delete_one({"_id": str(todo_id)})
    if result.deleted_count > 0:
        return True
    return False


def toggle_complete(todo_id):
    """Toggle the completed status of a todo."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if str(todo.get("_id", "")) == str(todo_id):
            collection.update_one({"_id": str(todo_id)}, {"$set": {"completed": not todo["completed"]}})
            return todos[i]
    
    return None


@app.route('/')
def index():
    """Render the main to-do list page."""
    todos = load_todos()
    return render_template('index.html', todos=todos)


@app.route('/api/todos', methods=['GET'])
def api_get_todos():
    """API endpoint to get all todos."""
    todos = load_todos()
    # Convert ObjectId to string for JSON serialization
    serialized_todos = []
    for todo in todos:
        if '_id' in todo and hasattr(todo['_id'], 'to_hex'):
            todo_copy = dict(todo)
            todo_copy['id'] = str(todo['_id'])
            serialized_todos.append(todo_copy)
        elif '_id' in todo:
            todo_copy = dict(todo)
            todo_copy['id'] = str(todo['_id'])
            serialized_todos.append(todo_copy)
        else:
            serialized_todos.append(todo)
    return jsonify(serialized_todos)


@app.route('/api/todos', methods=['POST'])
def api_create_todo():
    """API endpoint to create a new todo."""
    data = request.get_json()
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    
    if not description:
        return jsonify({'error': 'Description is required'}), 400
    
    todo = create_todo(description, priority)
    return jsonify(todo), 201


@app.route('/api/todos/<int:todo_id>', methods=['GET'])
def api_get_todo(todo_id):
    """API endpoint to get a single todo."""
    todos = load_todos()
    for todo in todos:
        if str(todo.get("_id", "")) == str(todo_id):
            return jsonify(todo)
    return jsonify({'error': 'Todo not found'}), 404


@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def api_update_todo(todo_id):
    """API endpoint to update a todo."""
    data = request.get_json()
    
    description = data.get('description')
    priority = data.get('priority')
    completed = data.get('completed')
    
    todo = update_todo(todo_id, description=description, priority=priority, completed=completed)
    if todo:
        return jsonify(todo)
    return jsonify({'error': 'Todo not found'}), 404


@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def api_delete_todo(todo_id):
    """API endpoint to delete a todo."""
    if delete_todo(todo_id):
        return jsonify({'message': 'Todo deleted successfully'})
    return jsonify({'error': 'Todo not found'}), 404


@app.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
def api_toggle_complete(todo_id):
    """API endpoint to toggle completion status."""
    todo = toggle_complete(todo_id)
    if todo:
        return jsonify(todo)
    return jsonify({'error': 'Todo not found'}), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
