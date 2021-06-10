from flask import Flask, render_template, request, jsonify
import requests, os
from urllib.parse import urlparse, urljoin
from flask import Flask, request, render_template, redirect, url_for, flash, abort, session
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user, UserMixin,
                         confirm_login, fresh_login_required)
from flask_wtf import FlaskForm as Form
from wtforms import BooleanField, StringField, PasswordField, validators
from passlib.hash import sha256_crypt as pwd_context
import json

###
# Globals
###

def hash_password(password):
    return pwd_context.using(salt="somestring").encrypt(password)

class LoginForm(Form):
    username = StringField('Username', [
        validators.InputRequired(u"Please, type in the username!"),
        validators.Length(min=2, max=25,
                          message=u"The username has to be 2-25 characters!")])
    password = PasswordField('Password', [
        validators.InputRequired(u"Please, type in the password!"),
        validators.Length(min=8, max=25,
                          message=u"The username has to be 8-25 characters!")])
    remember = BooleanField('Remember me')


class RegistrationForm(Form):
    username = StringField('Username', [
        validators.InputRequired(u"Please, type in the username!"),
        validators.Length(min=2, max=25,
                          message=u"The username has to be 2-25 characters!")])
    password = PasswordField('New Password', [
        validators.InputRequired(u"Please, type in the password!"),
        validators.Length(min=8, max=25,
                          message=u"The username has to be 8-25 characters!")])
    confirm = PasswordField('Repeat Password', [
        validators.InputRequired(u"Please, retype in the password!"),
        validators.EqualTo('password', message='Passwords must match!')])


def is_safe_url(target):
    """
    :source: https://github.com/fengsp/flask-snippets/blob/master/security/redirect_back.py
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username
        self.token = "Unknown"

    def set_token(self, token):
        self.token = token
        return self



app = Flask(__name__)
app.secret_key = "just a random secret key that nobody knows"

app.config.from_object(__name__)

login_manager = LoginManager()

login_manager.session_protection = "strong"

login_manager.login_view = "login"
login_manager.login_message = u"Please log in to access this page."

login_manager.refresh_view = "login"
login_manager.needs_refresh_message = (
    u"To protect your account, please reauthenticate to access this page."
)
login_manager.needs_refresh_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    user = None
    if 'id' in session and 'username' in session and 'token' in session:
        id = session['id']
        if id == user_id:
            username = session['username']
            token = session['token']
            user = User(id, username).set_token(token)
    return user

login_manager.init_app(app)

###
# Pages
###

#### requests.get('https://api.github.com').status_code

@app.route("/")
@app.route("/index")
def index():
    return render_template("index.html")


@app.route("/brevet")
@login_required
def brevet():
    return render_template("brevet_control_times.html")

@app.route("/<option>")
def display(option):
    token = current_user.token
    top = request.args.get("top", type=str)
    data_type = request.args.get("datatype", type=str)
    if (option == "listAll"):
        url = 'http://' + os.environ['BACKEND_ADDR'] + ':' + os.environ['BACKEND_PORT'] + '/listAll'
    elif (option == "listOpenOnly"):
        url = 'http://' + os.environ['BACKEND_ADDR'] + ':' + os.environ['BACKEND_PORT'] + '/listOpenOnly'
    else:
        url = 'http://' + os.environ['BACKEND_ADDR'] + ':' + os.environ['BACKEND_PORT'] + '/listCloseOnly'
    if data_type == "csv":
        url += '/csv'
    if int(top) > 0:
        url += '?top=' + top + '&token=' + token
    else:
        url += '?token=' + token
    r = requests.get(url).text
    if r == '"The database is empty. Please, submit the control time."\n':
        r = "empty"
    if data_type == "csv":
        r = r.replace('\\n', '<br/>')
        r = r.replace('"', '')
    return jsonify(result=r)



@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit() and request.method == "POST" \
            and "username" in request.form and "password" in request.form and "confirm" in request.form:
        username = request.form["username"]
        password = hash_password(request.form["password"])
        app.logger.debug(f"website: {password}")
        url = 'http://' + os.environ['BACKEND_ADDR'] + ':' + os.environ['BACKEND_PORT'] + '/register'
        post_req = requests.post(url, data={"username": username, "password": password})
        if post_req.status_code == 201:
            flash(post_req.json())
            return redirect(url_for('login'))
        else:
            error_msg = post_req.json()['message']
            flash(error_msg)
    return render_template("register.html", form=form)



@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit() and request.method == "POST" \
            and "username" in request.form and "password" in request.form:
        username = request.form["username"]
        password = hash_password(request.form["password"])
        url = 'http://' + os.environ['BACKEND_ADDR'] + ':' + os.environ['BACKEND_PORT'] \
              + '/token?username=' + username + '&password=' + password
        get_req = requests.get(url)
        if get_req.status_code == 201:
            get_req_json = json.loads(get_req.json())
            token = get_req_json['token']
            id = str(get_req_json['id'])
            remember = request.form.get("remember", "false") == "true"
            user = User(id, username).set_token(token)
            if login_user(user, remember=remember):
                session['id'] = id
                session['username'] = username
                session['token'] = token
                flash("Logged in!")
                flash("I'll remember you") if remember else None
                next = request.args.get("next")
                if not is_safe_url(next):
                    abort(400)
                return redirect(next or url_for('index'))
            else:
                flash("Sorry, but you could not log in.")
        else:
            error_msg = get_req.json()['message']
            flash(error_msg)
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop('id', None)
    session.pop('username', None)
    session.pop('token', None)
    flash("Logged out.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
