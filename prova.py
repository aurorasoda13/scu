
import psycopg2
from flask import Flask, render_template, request, redirect, session, send_file, jsonify
from datetime import timedelta

connection = psycopg2.connect(
    user="postgres.eyhuidxkqwegdjqfubfp",
    password="ks4grAGXzGAQm5w1",
    host="aws-0-eu-north-1.pooler.supabase.com",
    port=5432,
    dbname="postgres"
)

app = Flask(__name__)

id="24 AC 5E 30"

cursor = connection.cursor()
sql="SELECT nome FROM utente WHERE id = %s"
cursor.execute(sql, (id,))
result = cursor.fetchone() 
print(result) 
cursor.close()