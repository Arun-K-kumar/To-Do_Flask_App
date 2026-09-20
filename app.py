import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

TODO_FILE = "todos.json"


def load_todos():
    """Load todos from the JSON file."""
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_todos(todos):
    """Save todos to the JSON file."""
    with open(TODO_FILE, 'w') as f:
        json.dump(todos, f, indent=2)


def create_todo(description, priority="medium"):
    """Create a new todo item."""
    todos = load_todos()
    todo_id = len(todos) + 1
    todo = {
        "id": todo_id,
        "description": description,
        "priority": priority,
        "completed": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    todos.append(todo)
    save_todos(todos)
    return todo


def update_todo(todo_id, description=None, priority=None, completed=None):
    """Update an existing todo item."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
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
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            todos.pop(i)
            save_todos(todos)
            return True
    
    return False


def toggle_complete(todo_id):
    """Toggle the completed status of a todo."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            todos[i]["completed"] = not todos[i]["completed"]
            save_todos(todos)
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
    return jsonify(todos)


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
        if todo['id'] == todo_id:
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
