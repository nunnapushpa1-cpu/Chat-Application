# Flask Chat App

A simple Flask chat application with user login/signup and real-time messaging using Flask-SocketIO.

## Requirements

- Python 3.10+ (or compatible Python 3 release)
- A working internet connection to load Bootstrap and Socket.IO client files from CDN

## Setup and Run from Local Files

1. Open a terminal or PowerShell in this project folder:


2. Install the Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Run the app directly:
   ```powershell
   python app.py
   ```

4. Open your browser and go to:
   - `http://127.0.0.1:5001`

## App Behavior

- `/` shows the home page with login and signup options.
- `/signup` creates a new account.
- `/login` signs in an existing user.
- `/chat` opens the chat room for authenticated users.

## Notes

- The app uses a local SQLite database file: `users.db`.
- The database tables are created automatically when the app first starts.
- If you want to stop the server, press `Ctrl+C` in the terminal.
