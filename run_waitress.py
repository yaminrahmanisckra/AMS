from waitress import serve
from app import app

if __name__ == "__main__":
    print("Starting Academic Management System with Waitress server...")
    print("Server will be available at: http://localhost:5001")
    serve(app, host="0.0.0.0", port=5001, threads=4)
