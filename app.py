import json
import logging
import os
import re
import traceback
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from flask import Flask, render_template, request, jsonify, redirect, url_for
from bson import ObjectId
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

# Verify connection by running a ping command
try:
    result = client.admin.command('ping')
    print("MongoDB connection successful")
except Exception as e:
    error_msg = f"MongoDB connection failed: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    raise ConnectionError(f"Cannot connect to MongoDB: {e}") from e


def serialize_todo(todo):
    """Convert ObjectId to string for JSON serialization."""
    if '_id' in todo:
        # Convert ObjectId to string - this works for both ObjectId and regular strings
        todo_copy = dict(todo)
        todo_copy['id'] = str(todo['_id'])
        del todo_copy['_id']  # Remove the original _id field (still an ObjectId)
        return todo_copy
    return todo


def load_todos():
    """Load todos from MongoDB."""
    try:
        result = collection.find()
        todos = list(result)
        print(f"Loaded {len(todos)} todos from MongoDB")
        return todos
    except Exception as e:
        import traceback
        error_msg = f"Error loading todos: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise


def save_todos(todos):
    """Save todos to MongoDB."""
    collection.delete_many({})
    for todo in todos:
        collection.insert_one(todo)


def create_todo(description, priority="medium"):
    """Create a new todo item."""
    try:
        todos = load_todos()
        todo = {
            "description": description,
            "priority": priority,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        result = collection.insert_one(todo)
        if not result.acknowledged:
            raise Exception("Insert not acknowledged by MongoDB")
        todo['_id'] = str(result.inserted_id)
        return serialize_todo(todo)
    except Exception as e:
        print(f"Error creating todo: {e}")
        return None


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
            return serialize_todo(todos[i])
    
    return None


def delete_todo(todo_id):
    """Delete a todo item."""
    try:
        # Validate ObjectId format before conversion
        if not re.match(r'^[0-9a-fA-F]{24}$', str(todo_id)):
            logger.warning(f"Invalid ObjectId format for todo_id: {todo_id}")
            return False
        
        result = collection.delete_one({"_id": ObjectId(str(todo_id))})
        logger.info(f"Delete operation completed, deleted {result.deleted_count} document(s)")
        if result.deleted_count > 0:
            return True
        return False
    except ValueError as e:
        error_msg = f"ObjectId conversion error - invalid format: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Error deleting todo: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise


def toggle_complete(todo_id):
    """Toggle the completed status of a todo."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if str(todo.get("_id", "")) == str(todo_id):
            collection.update_one({"_id": ObjectId(str(todo_id))}, {"$set": {"completed": not todo["completed"]}})
            todos[i]["completed"] = not todo["completed"]
            return serialize_todo(todos[i])
    
    return None


@app.route('/')
def index():
    """Render the main to-do list page."""
    try:
        todos = load_todos()
        serialized_todos = [serialize_todo(todo) for todo in todos]
        return render_template('index.html', todos=serialized_todos)
    except Exception as e:
        import traceback
        print(f"Error loading todos for index: {traceback.format_exc()}")
        return render_template('index.html', todos=[]), 500


@app.route('/api/todos', methods=['GET'])
def api_get_todos():
    """API endpoint to get all todos."""
    try:
        todos = load_todos()
        serialized_todos = [serialize_todo(todo) for todo in todos]
        print(f"Successfully retrieved {len(serialized_todos)} todos")
        return jsonify(serialized_todos)
    except Exception as e:
        import traceback
        error_msg = f"Error getting todos: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': 'Failed to get todos', 'details': str(e)}), 500


@app.route('/api/todos', methods=['POST'])
def api_create_todo():
    """API endpoint to create a new todo."""
    try:
        data = request.get_json() or {}
        description = (data.get('description') or '').strip()
        priority = data.get('priority', 'medium')
        
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        
        # Validate priority
        valid_priorities = ['high', 'medium', 'low']
        if priority and priority not in valid_priorities:
            priority = 'medium'
        
        todo = create_todo(description, priority)
        if not todo:
            return jsonify({'error': 'Failed to create todo'}), 500
        
        return jsonify(todo), 201
    except Exception as e:
        import traceback
        print(f"Error creating todo: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to create todo'}), 500


@app.route('/api/todos/<todo_id>')
def api_get_todo(todo_id):
    """API endpoint to get a single todo."""
    try:
        todos = load_todos()
        for todo in todos:
            if str(todo.get("_id", "")) == str(todo_id):
                return jsonify(serialize_todo(todo))
        return jsonify({'error': 'Todo not found'}), 404
    except Exception as e:
        import traceback
        print(f"Error getting todo: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to get todo'}), 500


@app.route('/api/todos/<todo_id>', methods=['PUT'])
def api_update_todo(todo_id):
    """API endpoint to update a todo."""
    try:
        data = request.get_json() or {}
        
        description = (data.get('description') or '').strip() if data.get('description') else None
        priority = data.get('priority')
        completed = data.get('completed')
        
        # Validate priority if provided
        valid_priorities = ['high', 'medium', 'low']
        if priority and priority not in valid_priorities:
            return jsonify({'error': 'Invalid priority'}), 400
        
        todo = update_todo(todo_id, description=description, priority=priority, completed=completed)
        if not todo:
            return jsonify({'error': 'Todo not found'}), 404
        return jsonify(todo)
    except Exception as e:
        import traceback
        print(f"Error updating todo: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to update todo'}), 500


@app.route('/api/todos/<todo_id>', methods=['DELETE'])
def api_delete_todo(todo_id):
    """API endpoint to delete a todo."""
    try:
        # Validate ObjectId format before conversion
        if not re.match(r'^[0-9a-fA-F]{24}$', str(todo_id)):
            logger.warning(f"Invalid ObjectId format for todo_id in API request: {todo_id}")
            return jsonify({'error': 'Invalid todo ID format'}), 400
        
        result = collection.delete_one({"_id": ObjectId(str(todo_id))})
        logger.info(f"Delete operation completed, deleted {result.deleted_count} document(s)")
        if result.deleted_count > 0:
            todos = load_todos()
            serialized_todos = [serialize_todo(todo) for todo in todos]
            return jsonify({'message': 'Todo deleted successfully', 'todos': serialized_todos})
        return jsonify({'error': 'Todo not found'}), 404
    except ValueError as e:
        error_msg = f"ObjectId conversion error - invalid format: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return jsonify({'error': 'Invalid ObjectId format'}), 400
    except Exception as e:
        error_msg = f"Error deleting todo: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return jsonify({'error': f'Failed to delete todo: {str(e)}'}), 500


@app.route('/api/todos/<todo_id>/toggle', methods=['POST'])
def api_toggle_complete(todo_id):
    """API endpoint to toggle completion status."""
    try:
        todo = toggle_complete(todo_id)
        if not todo:
            return jsonify({'error': 'Todo not found'}), 404
        return jsonify(todo)
    except Exception as e:
        import traceback
        print(f"Error toggling todo: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to toggle todo'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
