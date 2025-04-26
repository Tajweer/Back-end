# init_db.py
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Parse database URL to get connection parameters
# Format: mysql+pymysql://username:password@host/dbname
db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:Tt121212@@localhost/tajweer")
parts = db_url.replace("mysql+pymysql://", "").split("@")
credentials = parts[0].split(":")
host_db = parts[1].split("/")

username = credentials[0]
password = credentials[1]
host = host_db[0]
dbname = host_db[1]

def create_database():
    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(
            host=host,
            user=username,
            password=password
        )
        
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Check if database exists and create if it doesn't
            cursor.execute(f"SHOW DATABASES LIKE '{dbname}'")
            result = cursor.fetchone()
            
            if not result:
                cursor.execute(f"CREATE DATABASE {dbname}")
                print(f"Database '{dbname}' created successfully.")
            else:
                print(f"Database '{dbname}' already exists.")
            
            conn.close()
            print("Connection closed.")
            
            return True
    
    except Error as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    create_database()