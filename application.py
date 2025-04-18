import pandas as pd
import pymongo
import secrets
import smtplib
import random
import matplotlib
matplotlib.use('Agg')
from werkzeug.security import generate_password_hash, check_password_hash
import matplotlib.pyplot as plt
import os
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask import flash
from datetime import datetime as dt
from dotenv import load_dotenv
import logging


# CREATING A FLASK APPLICATION
app = Flask(__name__)

# LOAD THE ENV FILE DATAS
load_dotenv()

# FETCHING THE CURRENT PROJECT ABSOLUTE PATH
logFilePath = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "allLog", "Logs.log"
)

# CREATE FILE IN CASE IF FILE NOT EXIST
os.makedirs(os.path.dirname(logFilePath), exist_ok=True)

# LOGGING CONFIGRATION SET UP
logging.basicConfig(
    filename=logFilePath,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)


# DATABASE CONNECTION WITH MONGODB
try:
    # MONGO DB URL
    mongo_url = os.environ.get("mongo_url")
    # CONNECT WITH MONGO DB
    Client = pymongo.MongoClient(mongo_url)
    # CREATING A DATABASE
    ExpenseDb = Client["ExpenseTracker"]
    # CREATING A COLLECTION
    userCollection = ExpenseDb["User"]
except Exception as e:
    # SAVING THE LOG INFO IN CASE ERROR OCCUR
    logging.info("Error Occured During MongoDB Connection ")


# FETCH THE SECRETE KEY FOR SESSION OR GENERATE NEW IN CASE NOT FOUND IN ENV FILE
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))



# LOGIN PAGE ROUTE
@app.route("/", methods=["POST", "GET"])
def login():
    logging.info(f"Login Page Fetched")
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            try:
                user = userCollection.find_one({"email": email})
            except:
                logging.info("Error In Finding User For Login ")
                return render_template("login.html", message="Something Went Wrong!")
            if user:
                if check_password_hash(user["password"], password):
                    # SAVE THE USER DETAILS IN THE SESSION
                    for key in ['_id', 'otp', 'password']:
                        user.pop(key, None) 
                    user['balance']=user['budget']-user['spent']
                    user['expenses']=user['expenses'][-5:]
                    session["user"] = user
                    # GENERATE THE GRAPH
                    generate_chart()
                    # SAVE LOG ON SUCCESSFUL LOGIN
                    logging.info(
                        f"Email : {email} Password : {password} :-Login Successfully & Session Saved Successfully!"
                    )
                    # DELETE ALL THE PREVIOUS CHART 
                    try:
                        file_path = os.path.join(app.static_folder, "chart.png")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"Deleted: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file: {e}")

                    # REDIRECT TO HOMEPAGE ROUTE
                    flash("Login Successfully!","success")
                    return redirect(url_for("homePage"))
                else:
                    logging.info(f"Invalid Password Password : {password}")
                    return render_template("login.html", message="Invalid Password")
            else:
                logging.info(f"Invalid Email Email : {email}")
                return render_template("login.html", message="Invalid Email")
        except Exception as e:
            logging.info("Error Occured In Login ")
            return render_template(
                "login.html", message="Something Went Wrong Please Try again"
            )
    else:
        return render_template("login.html")


# REGISTER PAGE ROUTE
@app.route("/register", methods=["POST", "GET"])
def register():
    logging.info("Register Page Fetched")
    if request.method == "POST":
        name = request.form.get("name").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password").strip()
        confirmpass = request.form.get("confirm_password").strip()
        # CHECK PASSWORD AND CONFIRM PASSWORD IS MATCHING OR NOT ?
        if password != confirmpass:
            logging.info(f"Password Not Matching For Register : Email :{email} Password :{password} : {confirmpass}")
            return render_template("register.html", message="Password Is Not Matching")
        # CHECK ANY OF THE VALUE IS INVALID OR NOT 
        if (
            len(name) == 0
            or len(email) == 0
            or len(password) == 0
            or len(confirmpass) == 0
        ):
            # IF FOUND INVALID DATA THEN RETURN TO REGISTER PAGE 
            logging.info("Inalid Data Found")
            return render_template("register.html", message="Invalid Credential")
        else:
            try:
                # CHECK FOR IS THE EMAIL ALREADY REGISTER OR NOT 
                user = userCollection.find_one({"email": email})
                if not user:
                    try:
                        # SAVE THE USER DATA INTO THE DATABASE 
                        userCollection.insert_one(
                            {
                                "name": name,
                                "email": email,
                                "password": generate_password_hash(password),
                                "expenses": [],
                                "budget": 0,
                                "spent": 0,
                            }
                        )
                    except Exception as e:
                        # IF ANY ERROR FOUND DURING SAVING USER DATA INTO DATABASE 
                        # SAVE THE LOG 
                        logging.info("Error Occured During Inserting User Data Into Database ")
                        # RETURN BACK TO THE REGISTER PAGE 
                        return render_template(
                        "register.html", message="SomeThing Went Wrong"
                    )
                    logging.info(f"Name :{name} Email:{email} Password:{password} :: User Register Successfully")
                    # ON SUCCESSFULLY REGISTRATION REDIRECT TO LOGIN PAGE 
                    return redirect(url_for("login"))
                else:
                    # IF EMAIL FOUND ALREADY REGISTERED 
                    # SAVE THE LOG 
                    logging.info("Email Already Registered!")
                    # RETURN BACK TO THE REGISTER PAGE 
                    return render_template(
                        "register.html", message="Email Already Registered"
                    )
            except Exception as e:
                logging.error("Something Went Wrong In Registering The User")
                return render_template(
                        "register.html", message="Internal Server Error"
                    )
    return render_template("register.html")


# HOME PAGE ROUTE
@app.route("/homePage", methods=["POST", "GET"])
def homePage():
    logging.info("Home Page Fetched ")
    # CHECK FOR VALID USER OR NOT BY CHECKING THE SESSION INFO
    if "user" in session:
        message = request.args.get("message", "")
        return render_template(
            "homePage.html",
            user=session['user']
        )
    else:
    # IF SESSION INFO IS NOT PRESENT THEN REDIRECT TO LOGIN PAGE 
    # SAVE THE LOG 
        logging.info("Unautherised User Trying To Access Home Page")
        return redirect(url_for("login"))


# ROUTE FOR ADDING EXPENSE
@app.route("/add_expense", methods=["POST", "GET"])
def add_expense():
    logging.info("Add Expense Request Fetched")
    if request.method == "POST":
        # FETCH THE USER EMAIL FROM SESSION 
        userData=session.get("user")
        email = userData['email']
        
        # FETCHING THE DATA FROM THE FORM DATA 
        title = request.form.get("title").strip()
        amount = int(request.form.get("amount").strip())
        date = request.form.get("date").strip()
        category = request.form.get("category").strip()
        # CHECK FOR DATA IS VALID OR NOT 
        if len(title) == 0 or len(date) == 0 or len(category) == 0:
            logging.info("Invalid Data Filled By User")
            flash("Invalid Data Found!", "error")
            return redirect(url_for("homePage"))
        else:
            # CREATE A DICTIONARY OF EXPENSE FOR ADDING INTO THE EXPENSES
            data = {
                "date": date,
                "amount": amount,
                "title": title,
                "category": category,
            }
            try:
                # ADD THE NEW EXPENSE INTO THE DATABSE 
                updatedData = userCollection.find_one_and_update(
                    {"email": email},
                    {"$push": {"expenses": data}, "$inc": {"spent": amount}},
                    return_document=pymongo.ReturnDocument.AFTER,
                )
                # UPDATE THE DATA INTO SESSION AND HOME PAGE
                for key in ['_id', 'otp', 'password']:
                        updatedData.pop(key, None) 
                updatedData['balance']=updatedData['budget']-updatedData['spent']
                updatedData['expenses']=updatedData.get("expenses")[-5:]
                session['user']=updatedData
                
                # SAVE THE LOG 
                logging.info(f"Expense Added Successfully,Updated Data : {updatedData}")
                # GENERATE CHART FOR UPDATED DATA 
                generate_chart()
                
                # RERENSER THE PAGE WITH UPDATED DATA 
                flash("Expense Added Successfully!","success")
                return redirect(url_for("homePage"))
            except Exception as e:
                logging.info("Error Occured During Adding Expense ")
                flash("Something went wrong!","error")
                return redirect(url_for("homePage"))
    else:
        # IF UNAUTHERISED USER WNAT TO ACCESS THE ROUTE 
        logging.info("Unautherised User Trying To User Add Expense Route")
        return redirect(url_for("login"))


# ADD BUDGET ROUTE 
@app.route("/add_budget", methods=["POST", "GET"])
def add_budget():
    logging.info("Add Budget Request Fetched")
    if request.method == "POST":
        # FETCHING THE DATA FROM SESSION OR REQUEST FORM 
        userData=session['user']
        email = userData['email']
        amount = int(request.form.get("budget_amount").strip())
        try:
            # ADDING THE BUDGET INTO THE DATABSE 
            updatedData = userCollection.find_one_and_update(
                {"email": email},
                {"$inc": {"budget": amount}},
                return_document=pymongo.ReturnDocument.AFTER,
            )
            
            # UPDATE THE DATA INTO SESSION AND HOME PAGE
            for key in ['_id', 'otp', 'password']:
                updatedData.pop(key, None) 
                
            updatedData['expenses']=updatedData.get("expenses")[-5:]
            updatedData['balance']=amount-updatedData['spent']
            session["user"] = updatedData
            
            # SAVE THE LOG 
            logging.info(f"Budget Added Successfully,Updated Data : {updatedData}")
            
            # RERENDER THE PAGE WITH UPDATED DATA 
            flash("Budget Added Successfully!", "success")
            return redirect(url_for("homePage"))
        except Exception as e:
            logging.info("Something Went Wrong In Adding Budget ")
            flash("Something Went Wrong!","error")
            return redirect(url_for("homePage"))
    else:
        # IF UNAUTHERISED USER WANT TO ACCESS THIS ROUTE 
        # SAVE THE LOG 
        logging.info("Unautherised User Want To Access The Add Budget Route")
        # REDIRECT TO LOGIN PAGE 
        return redirect(url_for("login"))


# RESET ALL FUNCTION CODE
@app.route("/reset_all", methods=["POST", "GET"])
def reset_all():
    logging.info("Reset All Request Fetched ")
    if "user" in session:
        # FETCH THE DATA FROM SESSION 
        userData=session['user']
        email = userData['email']
        try:
            # RESET ALL THE DATA EXCEPT THE LIST OF EXPENSES 
            updatedData = userCollection.find_one_and_update(
                {"email": email},
                {"$set": {"budget": 0, "spent": 0}},
                return_document=pymongo.ReturnDocument.AFTER,
            )
            
            # UPDATE IN THE SESSION
            for key in ['_id', 'otp', 'password']:
                updatedData.pop(key, None) 
            updatedData['balance']=updatedData['budget']-updatedData['spent']
            updatedData['expenses']=updatedData.get("expenses")[-5:]
            session['user']=updatedData
            # SAVE THE LOG 
            logging.info(f"Reset Successfully,Updated Data : {updatedData}")
            # RETURN THE HOME PAGE WITH UPDATED DATA
            flash("Data Reset Successfully","success")
            return redirect(url_for("homePage"))
        except Exception as e:
            logging.info("Something Went Wrong During Reset All ")
            flash("Something Went Wrong!","error")
            return redirect(url_for("homePage"))
    else:
        # IF UNAUTHERISED USER TRY TO ACCESS THIS ROUTE 
        logging.info("Unautherised User Is Trying To Access The Reset All Route ")
        # REDIRECT BACK TO LOGIN PAGE 
        return redirect(url_for("login"))


# LOGOUT FUNCTION
@app.route("/logout", methods=["POST", "GET"])
def logout():
    logging.info("Log Out Request Fetched")
    if "user" in session:
        userData=session['user']
        # DELETE THE GRAPH 
        try:
            file_path = os.path.join(app.static_folder, f"{userData['name']}.png")
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Graph Deleted : {file_path}")
        except Exception as e:
            logging.info("Error In Deleteing The File ")
        # CLEARING THE SESSION DATA 
        session.clear()
        # RETURN BACK TO THE LOGIN PAGE 
        return redirect(url_for("login"))
    else:
        # IF UNAUTHERISED USER TRY TO ACCESS THIS ROUTE 
        logging.info("Unautherised User Try To Access The Log Out Route")
        return redirect(url_for("login"))

# RESET PASSWORD ROUTE 
@app.route("/resetPassword", methods=["POST", "GET"])
def resetPassword():
    logging.info("Reset Password Request Fetched ")
    if "email" in session:
        if request.method == "POST":
            # FETCH THE DATA FROM THE FORM 
            email = session.get("email")
            password = request.form.get("new_password")
            newPassword = request.form.get("confirm_password")
            if password == newPassword:
                try:
                    # UPADTE THE PASSWORD IN THE DATABSE 
                    userCollection.find_one_and_update(
                        {"email": email}, {"$set": {"password": password}}
                    )
                    logging.info(f"Email :{email},Password :{password} [Password Reset Successfully]")
                    session.clear()
                    return redirect(url_for("login"))
                except Exception as e:
                    logging.info("Error During Updating Password")
                    return render_template(
                        "resetPassword.html", message="Something Went Wrong"
                    )
            else:
                logging.info("Password Is Not Matching For Reset Password")
                return render_template(
                    "resetPassword.html", message="Password Not Matching"
                )
        else:
            return render_template("resetPassword.html")
    else:
        # IF UNAUTHERISED USER TRY TO ACCESS THIS ROUTE 
        # SAVE THE LOG 
        logging.info("Unautherised User Try To Access The Forgot Password Route")
        # REDIRECT USER TO THE LOGIN PAGE 
        return redirect(url_for("forgot_password"))


# FORGOT PASSWORD ROUTE
@app.route("/forgot_password", methods=["POST", "GET"])
def forgot_password():
    logging.info("Forgot Password Request Fetched")
    if request.method == "POST":
        # FETCH THE DATA FROM SESSION OR FORM 
        email = request.form.get("email")
        
        # FETCH THE USER FROM THE DATABASE 
        user = userCollection.find_one({"email": email})
        
        # CHECK USER FOUND OR NOT 
        if user:
            # CHECK OTP IS AVAILABLE IN REUEST FORM OR NOT 
            try:
                otp = request.form.get("otp")
            except:
                logging.info("Error Occured While Fetching Otp From Form")
                return render_template("forgotPassword.html", email=email)
            if otp:
                # IF OTP FOUND IN THE FORM 
                # VERIFY THE OTP 
                if verify_otp(otp):
                    # SAVE THE LOG 
                    logging.info("OTP Verified Successfully")
                    # REDIRECT TO RESET PASSWORD ROUTE 
                    return redirect(url_for("resetPassword"))
                else:
                    # IF OTP IS INCORRECT 
                    # SAVE THE LOG 
                    logging.info("Incorrect OTP")
                    # RERENDER THE FORGOT PASSWORD PAGE 
                    return render_template(
                        "forgotPassword.html", message="Incorrect OTP", email=email
                    )
            else:
                # IF OTP NOT FOUND IN FORM MEAN OTP NOT SENT TO USERS EMAIL 
                # SEND THE OTP TO USER EMAIL 
                send_mail(email)
                logging.info(f"OTP Sent To Email : {email}")
                # SAVE THE EMAIL INTO THE SESSION 
                session["email"] = email
                # RERENDER THE FORGOT PASSWORD PAGE 
                return render_template(
                    "forgotPassword.html",
                    message=f"OTP Sent Successfully On {email}",
                    email=email,
                )
        else:
            # IF NO USER FOUND WITH GIVEN EMAIL THEN 
            # SAVE THE LOG 
            logging.info("Invalid Email For Forgot Password")
            return redirect(url_for("forgotPassword.html", "Invalid Email"))
    else:
        return render_template("forgotPassword.html")


# FUNCTION TO VERIFY OTP
def verify_otp(otp):
    logging.info("Verify OTP Function Called ")
    email = session["email"]
    # FETCH THE USER FROM THE DATABASE USING EMAIL 
    user = userCollection.find_one({"email": email})
    if user["otp"] == otp:
        logging.info("OTP Is Correct")
        return True
    else:
        logging.info("OTP Is Incorrect")
        return False


# SEND MAIL FUNCTION CODE
def send_mail(email):
    logging.info("Send Mail Fucntion Called ")
    sender_email = os.environ.get("sender_email")
    sender_password = os.environ.get("sender_password")

    # Setup the MIME
    message = MIMEMultipart()
    message["From"] = f"ExpenseTracker <{os.environ.get('sender_email')}>"
    message["To"] = email
    message["Subject"] = "OTP To Forgot Password"
    num = random.randint(1000, 9999)

    # Body of the email
    body = (
        f"Dear User,\n\n"
        f"We have received a request to reset your password for your ExpenseTracker account.\n\n"
        f"Your One-Time Password (OTP) for resetting your password is: {num}\n\n"
        f"Please use this OTP within the next 10 minutes to complete your password reset process.\n\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"Thank you for using ExpenseTracker.\n\n"
        f"Best Regards,\n"
        f"ExpenseTracker Team"
    )

    message.attach(MIMEText(body, "plain"))

    # Sending the email via Gmail's SMTP server
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        text = message.as_string()
        server.sendmail(sender_email, email, text)
        server.quit()
        userCollection.find_one_and_update(
            {"email": email}, {"$set": {"otp": str(num)}}
        )
        logging.info(f"OTP Sent To Email : {email},OTP : {num}")
        return True
    except Exception as e:
        logging.info("Failed To Send The Email")
        return False


# DOWNLOAD EXPENSE ROUTE
@app.route("/download_expense", methods=["POST", "GET"])
def download_expense():
    logging.info("Download Expense Request Fetched")
    if request.method == "POST":
        userData=session['user']
        email = userData["email"]
        category = request.form.get("category")
        user = userCollection.find_one({"email": email})

        if user and "expenses" in user:
            # Always sort first
            sorted_expenses = sorted(
                user["expenses"], key=lambda x: dt.strptime(x["date"], "%Y-%m-%d")
            )

        if category == "1":
            data = sorted_expenses[-7:]
            filename = "weekly_expense.csv"
        elif category == "2":
            data = sorted_expenses[-30:]
            filename = "monthly_expense.csv"
        else:
            data = sorted_expenses
            filename = "all_expense.csv"
        # CONVERTING DATA INTO PANDAS DATAFRAME
        df = pd.DataFrame(data)
        # CONVERT DATAFRAME INTO CSV FILE
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        # SENDING RESPONSE
        return Response(
            csv_buffer,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        # IF UNAUTHERISED USER TRY TO ACCESS THIS ROUTE 
        # SAVE THE LOG 
        logging.info("Unautherised User Trying To Access The Downlaod Expense Route ")
        # REDIRECT THE USER TO LOGIN PAGE 
        return redirect(url_for("login"))


# VISUALISE EXPENSE USING CHART
def generate_chart():
    logging.info("Generate Chart Function Called ")
    # FETCH THE DATA FROM THE SESSION 
    try:
        userData=session['user']
        email = userData["email"]
        # FINDING THE USER FROM THE DATABSE USING GIVEN EMAIL 
        user = userCollection.find_one({"email": email})
        if user:
            # IF USER FOUND 
            if len(user["expenses"]) != 0:
                try:
                    sorted_expenses = sorted(
                        user["expenses"], key=lambda x: dt.strptime(x["date"], "%Y-%m-%d")
                    )
                    monthly_data = sorted_expenses[-30:]
                except Exception as e:
                    logging.info(f"No Expense Found Or Something Went Wrong In Sorting The Expense")
                
                # CREATING A PANDAS DATAFRAME
                df = pd.DataFrame(monthly_data)
                
                # GROUP THE DATA INTO DATE AND AMOUNT FORM DATE IS INDEX AND AMOUNT WILL VALUE 
                grouped = df.groupby("date")["amount"].sum().sort_values(ascending=False)
                
                # SET THE CHART FIGURE SIZE 
                plt.figure(figsize=(8, 6))
                # PLOTING THE BAR CHART WITH BLUE COLOR 
                grouped.plot(kind="bar", color="skyblue")
                # SET THE TITLE OF THE CHART 
                plt.title("Monthly Expense by Date")
                # SET THE NAME OF Y AXIS VALUE 
                plt.ylabel("Amount (₹)")
                # SET THE NAME FOR X AXIS VALUE 
                plt.xlabel("Date")
                plt.tight_layout()
                
                # FETCHING THE CURRENT WORKING PROJECT ABSOLUTE PATH 
                base_dir = os.path.dirname(os.path.abspath(__file__)) + "/static"
                # CREATING NEW PATH FOR SAVING THE CHART 
                chart_path = os.path.join(base_dir, f"{userData['name']}.png")
                # IF FOLDER (STATIC) NOT EXIST THEN CREATE 
                if not os.path.exists(base_dir):
                    os.makedirs(base_dir)
                # SAVE THE CHART IN THE CREATED PATH 
                plt.savefig(chart_path)
                # CLOSE THE PLOTING 
                plt.close()
                logging.info("Chart Prepared Successfully")
            else:
                logging.info("No Expense Found")
        else:
            logging.info(f"Invalid Email: No USer Found With Email {email}")
    except Exception as  e:
        logging.error(f"Something Went Wrong During Generating Chart : {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
