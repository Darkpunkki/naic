
# Database Connection

## Overview
This project uses environment variables to determine which database to connect to (MySQL or PostgreSQL). The database connection settings are configured in `init_db.py`.

## Configuration Steps
1. Set the `DB_TYPE` environment variable to either:
   - `mysql`
   - `psql`
2. If using MySQL, set:
   - `MYSQL_USERNAME` to your MySQL username
   - `MYSQL_PASSWORD` to your MySQL password
   - (Optionally) `MYSQL_URI` if you have a custom URI
3. If using PostgreSQL, set:
   - `PSQL_USERNAME` to your PostgreSQL username
   - `PSQL_PASSWORD` to your PostgreSQL password
   - (Optionally) `PSQL_URI` if you have a custom URI
4. Optionally, set `SECRET_KEY` for Flask session security.

## Running the App
1. Install dependencies:  
   ```
   pip install -r requirements.txt
   ```
2. Launch the Flask server:  
   ```
   flask run
   ```
3. If tables do not exist, the app will create them automatically at startup.

## Troubleshooting
- Ensure your environment variables are correct.
- Verify the database service is running locally or remotely.
- Check logs to confirm successful connections.