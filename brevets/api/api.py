from flask import Flask, request, abort
from flask_restful import Resource, Api, reqparse
from bson import json_util
import json
import db # Database operations
import os
#from passlib.apps import custom_app_context as pwd_context
from passlib.hash import sha256_crypt as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer \
                                  as Serializer, BadSignature, \
                                  SignatureExpired)

app = Flask(__name__)
api = Api(app)

client = db.Mongodb(os.environ['MONGODB_HOSTNAME'])
client.connect()
client.set_data("brevetsdb")

parser = reqparse.RequestParser()
parser.add_argument('username', required=True, help="Need an username!")
parser.add_argument('password', required=True, help="Need a password!")

SECRET_KEY = "nobodyknowsthekey272781239@#!"

def _csv(rows):
    h = list(rows[0].keys())
    result = ",".join(h) + "\n"
    for row in rows:
        row_val = [str(r) for r in list(row.values())]
        result += ",".join(row_val) + "\n"
    return result

def hash_password(password):
    return pwd_context.using(salt="somestring").encrypt(password)

def verify_password(password, hashVal):
    return pwd_context.verify(password, hashVal)

def generate_auth_token(id, expiration=60):
   s = Serializer(SECRET_KEY, expires_in=expiration)
   return s.dumps({'id': id})

def verify_auth_token(token):
    s = Serializer(SECRET_KEY)
    try:
        data = s.loads(token)
    except SignatureExpired:
        return None    
    except BadSignature:
        return None    
    return "Success"

class register(Resource):
    def post(self):
        client.set_collection("user")
        info = parser.parse_args()
        if not (2 <= len(info['username']) <= 25):
            return abort(400, "The username has to be 2-25 characters!")
        app.logger.debug(f"before: {info['password']}")
        info['password'] = hash_password(info['password'])
        app.logger.debug(f"after: {info['password']}")
        if len(client.f_find([], {'username': info['username']})) == 0:
            info['id'] = client.generate_id()
            client.insert(info)
            return "Registrarion Successful!", 201
        else:
            return abort(400, "This account has already been created!")


class token(Resource):
    def get(self):
        client.set_collection("user")
        username = request.args.get("username", default="")
        password = request.args.get("password", default="")
        if username == "" or password == "":
            return abort(400, "Need both username and password!")
        info = client.f_find(["id", "password"], {'username': username})
        if info:
            info = info[0]
            id = info["id"]
            auth = {"id": id, "duration": 600}
            hashed_ = info["password"]
            app.logger.debug(f"password: {password}, hashed: {hashed_}, verify: {verify_password(password, hashed_)}")
            if verify_password(password, hashed_):
                auth["token"] = generate_auth_token(id).decode("utf-8")
                return json.dumps(auth), 201
            return abort(400, "Incorrect password. Please try again!")
        else:
            return abort(400, "This username does not exist. PLease register first and try agian")


class listAll(Resource):
    def get(self, option="", dtype=""):
        client.set_collection("latestsubmit")
        top = int(request.args.get("top", default=-1))
        # Get the argument token; default value will be ""
        user_token = request.args.get("token", default="")
        if not verify_auth_token(user_token):
            return abort(400, "Authentication failed!")
        else:
            if option == "All":
                fields = ["km", "open", "close"]
            elif option == "OpenOnly":
                fields = ["km", "open"]
            elif option == "CloseOnly":
                fields = ["km", "close"]
            else:
                return "The only possible options are listAll, listOpenOnly, listCloseOnly!"

            if top > 0:
                rows = client.f_top(fields, top)
            elif top == -1:
                rows = client.f_find(fields)
            else:
                return "Need to enter a positive integer for top!"
            if len(rows) == 0:
                return "The database is empty. Please, input the control time."
            if dtype == 'csv':
                result = _csv(rows)
            elif dtype == 'json' or dtype == "":
                result = json.loads(json_util.dumps(rows))
            else:
                result = "The data can be displayed in both csv or json format. Try 'csv' or 'json'."
            return result

#############

api.add_resource(listAll, '/list<string:option>', '/list<string:option>/<string:dtype>')
api.add_resource(register, '/register')
api.add_resource(token, '/token')


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
