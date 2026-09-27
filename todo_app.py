import json
import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

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
        "id": todo_id,
        "description": description,
        "priority": priority,
        "completed": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    collection.insert_one(todo)
    print(f"✓ Todo created with ID: {todo_id}")
    return todo


def read_todos():
    """Display all todos."""
    todos = load_todos()
    if not todos:
        print("No todos found. Create one first!")
        return
    
    print("\n=== Your Todos ===")
    for todo in todos:
        status = "✓" if todo["completed"] else "○"
        priority_color = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}
        priority_display = priority_color.get(todo['priority'], '[?]')
        print(f"{todo['id']}. {status} [{priority_display}] {todo['description']}")
        print(f"   Created: {todo['created_at']}")
    print()


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
            print(f"✓ Todo {todo_id} updated!")
            return
    
    print(f"✗ No todo found with ID: {todo_id}")


def delete_todo(todo_id):
    """Delete a todo item."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            collection.delete_one({"id": todo_id})
            save_todos(todos)
            print(f"✓ Todo {todo_id} deleted!")
            return
    
    print(f"✗ No todo found with ID: {todo_id}")


def toggle_complete(todo_id):
    """Toggle the completed status of a todo."""
    todos = load_todos()
    
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            collection.update_one({"id": todo_id}, {"$set": {"completed": not todo["completed"]}})
            save_todos(todos)
            status = "completed" if todos[i]["completed"] else "incomplete"
            print(f"✓ Todo {todo_id} is now {status}!")
            return
    
    print(f"✗ No todo found with ID: {todo_id}")


def show_menu():
    """Display the main menu."""
    print("\n=== To-Do App ===")
    print("1. Create a new todo")
    print("2. View all todos")
    print("3. Update a todo")
    print("4. Delete a todo")
    print("5. Toggle completion status")
    print("6. Exit")


def get_priority():
    """Get priority from user input."""
    while True:
        priority = input("Enter priority (high/medium/low): ").lower()
        if priority in ["high", "medium", "low"]:
            return priority
        print("Invalid priority. Please enter high, medium, or low.")


def main():
    """Main application loop."""
    while True:
        show_menu()
        choice = input("Select an option (1-6): ").strip()
        
        if choice == "1":
            description = input("Enter todo description: ")
            priority = get_priority()
            create_todo(description, priority)
        
        elif choice == "2":
            read_todos()
        
        elif choice == "3":
            todo_id = int(input("Enter todo ID to update: "))
            print("\nUpdate options (leave blank to skip):")
            description = input(f"New description for todo {todo_id}: ").strip()
            priority = input(f"New priority for todo {todo_id}: ").strip()
            completed = input(f"Mark as completed? (y/n): ").strip().lower()
            
            if description:
                description = description
            if priority:
                priority = get_priority()
            if completed == "y":
                completed = True
            elif completed == "n":
                completed = False
            
            update_todo(todo_id, description=description, priority=priority, completed=completed)
        
        elif choice == "4":
            todo_id = int(input("Enter todo ID to delete: "))
            delete_todo(todo_id)
        
        elif choice == "5":
            todo_id = int(input("Enter todo ID to toggle: "))
            toggle_complete(todo_id)
        
        elif choice == "6":
            print("Goodbye!")
            break
        
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
