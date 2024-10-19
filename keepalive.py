import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path='keys.env')

DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL')

def keep_database_alive():
    # Use your actual connection string
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()

    # Run a simple query to keep the database alive
    cursor.execute("SELECT 1;")
    connection.commit()

    print("Database keep-alive query executed successfully!")

    # Close the connection
    cursor.close()
    connection.close()

if __name__ == "__main__":
    keep_database_alive()
