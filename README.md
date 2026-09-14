# Street Racer

Street Racer is a simple 2D top-down racing game built with HTML5 Canvas, JavaScript, Flask, and MySQL.

## Project structure

- `app.py` - Python Flask server and API routes
- `templates/index.html` - main game UI and screens
- `static/css/style.css` - racing theme styling
- `static/js/game.js` - canvas game and frontend logic
- `database/schema.sql` - MySQL database schema

## Setup

1. Open a terminal in the project folder.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate it:
   ```bash
   .venv\Scripts\activate
   ```
4. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
5. Start MySQL locally and create a database named `street_racer_db` or set the values in `.env`.
6. Copy `.env.example` to `.env` and update your MySQL credentials.
7. Run the app:
   ```bash
   python app.py
   ```
8. Open http://localhost:5000 in your browser.

## Game controls

- Left / A: move left
- Right / D: move right
- Up / W: increase speed
- Down / S: reduce speed
- Space: pause/resume

## API endpoints

- `POST /api/register`
- `POST /api/login`
- `POST /api/scores`
- `GET /api/scores`
- `GET /api/scores/top`
- `GET /api/player/<name>`

## Notes

This project is intentionally beginner-friendly and easy to understand. The frontend is browser-based, while the backend handles leaderboard data and player records.
