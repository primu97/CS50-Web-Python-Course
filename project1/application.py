import os
import requests

from flask import Flask, session, render_template, request, flash, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/registration", methods=["GET","POST"])
def registration():
     if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount:
            flash("Username already taken!")
        else:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": password})
            db.commit()
            return redirect(url_for(login))
     return render_template("registration.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username": username, "password": password}).fetchone()
        if user == None:
            return "ERROR"
        else:
            session['logged_in'] = True
            session['username'] = username

            return redirect(url_for('search'))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('username', None)
    session['logged_in'] = False
    return redirect(url_for('index'))

@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        find = '%' + request.form.get("word") + '%'

        results = db.execute("SELECT * FROM books WHERE title LIKE :find UNION SELECT * FROM books WHERE author LIKE :find UNION SELECT * FROM books WHERE isbn LIKE :find", {"find": find}).fetchall()
        return render_template("results.html", results=results)
    return render_template("search.html")

@app.route("/book/<int:book_id>", methods=["GET", "POST"])
def book(book_id):
    if request.method == "POST":
        review = request.form.get("review")
        rating = request.form.get("rating")
        if int(rating) < 1 or int(rating) > 5:
            return "PLS enter number from 1 to 5"
        user_id = db.execute("SELECT id FROM users WHERE username = :username", {"username" : session['username']}).fetchone()
        if db.execute("SELECT * FROM reviews JOIN users ON users.id = reviews.user_id JOIN books ON books.id = reviews.book_id WHERE user_id = :user_id AND reviews.book_id = :book_id", {"user_id": user_id.id, "book_id": book_id}).rowcount == 0:
            db.execute("INSERT INTO reviews (rating, review, book_id, user_id) VALUES (:rating, :review, :book_id, :user_id)", {"rating": rating, "review": review, "book_id": book_id, "user_id": user_id.id})
        else:
            return "ERROR"
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    reviews = db.execute("SELECT r.review, r.rating,  u.username FROM reviews AS r INNER JOIN users AS u ON  r.user_id = u.id INNER JOIN books AS b ON r.book_id = b.id WHERE b.id = :book_id", {"book_id": book_id}).fetchall()
    if not reviews:
        reviews = []
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "H8tD1rOfs3TrzYIpPEtHgA", "isbns": book.isbn})
    if res.status_code != 200:
        raise Exception("Error with request to Goodreads")
    g_avg_r = res.json()['books'][0]['average_rating']
    g_count_r = res.json()['books'][0]['work_ratings_count']
    return render_template("book.html", reviews=reviews, book=book, rating=g_avg_r, count=g_count_r)

@app.route("/api/<string:isbn>")
def book_api(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404

    review = db.execute("SELECT COUNT(review) AS count, AVG(rating) AS avg FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchone()
    return jsonify({
    "title": book.title,
    "author": book.author,
    "year": book.year,
    "isbn": isbn,
    "review_count": review.count,
    "average_score": review.avg
    }), 200
