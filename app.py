#!/usr/bin/env python3

import os
import sys
import subprocess
import datetime

from flask import Flask, render_template, request, redirect, url_for, session, make_response

# from markupsafe import escape
import pymongo
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
from dotenv import load_dotenv


# load credentials and configuration options from .env file
# if you do not yet have a file named .env, make one based on the template in env.example
load_dotenv(override=True)  # take environment variables from .env.

# instantiate the app using sentry for debugging
app = Flask(__name__)
app.secret_key = 'your secret key'

# # turn on debugging if in development mode
# app.debug = True if os.getenv("FLASK_ENV", "development") == "development" else False

# try to connect to the database, and quit if it doesn't work
try:
    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]  # store a reference to the selected database

    # verify the connection works by pinging the database
    cxn.admin.command("ping")  # The ping command is cheap and does not require auth.
    print(" * Connected to MongoDB!")  # if we get here, the connection worked!
except ConnectionFailure as e:
    # catch any database errors
    # the ping command failed, so the connection is not available.
    print(" * MongoDB connection error:", e)  # debug
    sys.exit(1)  # this is a catastrophic error, so no reason to continue to live


# set up the routes

@app.route("/", methods = ["GET"])
def home():
    """
    Route for the home page.
    Simply returns to the browser the content of the index.html file located in the templates folder.
    """
    return render_template("home.html")


@app.route("/login", methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        #checking if user/pass match to existing record within db
        user = db.users.find_one({"username": username})
        if user:
            #checking if password matches
            if user["password"] == password:
                session["username"] = username
                return redirect(url_for("home"))
            else:
                #given an incorrect password
                error_message = "Incorrect Password. Please try again!"
                return render_template("login.html", error = error_message)
            
        else:
            #if username is invalid
            error_message = "Username not found. Please register or try again."
            return render_template("login.html", error = error_message)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("home"))


@app.route("/register", methods = ["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        existing_user = db.users.find_one({"username": username})
        if existing_user:
            error = "Username already exists"
            return render_template("register.html", error=error)
        else:
            db.users.insert_one({"username": username, "password": password})
            session["username"] = username
            return redirect(url_for("workout_plans"))
    
    return render_template("register.html")


@app.route("/workout_plans", methods=["GET"])
def workout_plans():
    """
    Route for GET requests to the read page.
    Displays some information for the user with links to other pages.
    """
    plans = list(db.workout_plans.find({})) 
    sorted_plans = []
    for plan in plans:
        plan["_id"] = str(plan["_id"])
        plan["created_at"] = plan["created_at"].strftime("%m-%d-%Y %H:%M:%S")
        sorted_plans.append(plan)
    # Sort plans by created_at timestamp in descending order
    return render_template("workout_plans.html", plans=sorted_plans)


@app.route("/add_workout_plan", methods=["GET"])
def add_workout_plan_form():
    """
    Route for GET requests to the add workout page.
    Displays a form to fill out to create new workout.
    """
    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("add_workout_plan.html")


@app.route("/add_workout_plan", methods=["POST"])
def add_workout_plan():
    """
    Route for POST requests to the add workouts page
    Accepts the form submission data for a new document and saves the document to the database.
    """
    if "username" not in session:
        return redirect(url_for("login"))

    form = request.form.to_dict()
    title = form["title"]
    workout_type = form["type"]
    description = form["description"]
    created_by = session["username"]
    created_at = datetime.datetime.utcnow()

    db.workout_plans.insert_one({
        "title": title,
        "workout_type": workout_type,
        "description": description,
        "created_by": created_by,
        "created_at": created_at
    })

    return redirect(url_for("workout_plans"))


@app.route("/delete_workout_plan/<workout_id>")
def delete_workout_plan(workout_id):
    if "username" not in session:
        return redirect(url_for("login"))

    # Fetch the workout plan from the database
    workout = db.workout_plans.find_one({"_id": ObjectId(workout_id)})

    # Check if the logged-in user is the creator of the workout
    if workout["created_by"] != session["username"]:
        return "Unauthorized", 403  # Return a 403 Forbidden error

    # Delete the workout plan from the database
    db.workout_plans.delete_one({"_id": ObjectId(workout_id)})

    return redirect(url_for("workout_plans"))


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    GitHub can be configured such that each time a push is made to a repository, GitHub will make a request to a particular web URL... this is called a webhook.
    This function is set up such that if the /webhook route is requested, Python will execute a git pull command from the command line to update this app's codebase.
    You will need to configure your own repository to have a webhook that requests this route in GitHub's settings.
    Note that this webhook does do any verification that the request is coming from GitHub... this should be added in a production environment.
    """
    # run a git pull command
    process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
    pull_output = process.communicate()[0]
    # pull_output = str(pull_output).strip() # remove whitespace
    process = subprocess.Popen(["chmod", "a+x", "flask.cgi"], stdout=subprocess.PIPE)
    chmod_output = process.communicate()[0]
    # send a success response
    response = make_response(f"output: {pull_output}", 200)
    response.mimetype = "text/plain"
    return response


@app.errorhandler(Exception)
def handle_error(e):
    """
    Output any errors - good for debugging.
    """
    return render_template("error.html", error=e)  # render the edit template


# run the app
if __name__ == "__main__":
    # logging.basicConfig(filename="./flask_error.log", level=logging.DEBUG)
    app.run(load_dotenv=True, debug=True)
