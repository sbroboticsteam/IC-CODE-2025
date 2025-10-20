import socket
import json
import time
import flask
import requests
from flask import request

app = flask.Flask(__name__)
app.debug = False
class GameViewer():
    def __init__(self):
        # self.app = flask.Flask(__name__)
        self.app = app
        self.scores = {}
        pass

    def run(self):
        self.app.run(host="0.0.0.0", port=8080)

    @app.route("/")
    def index():
        return "<p>Hello, World!</p>"

    @app.route("/robots", methods = ["PUT"])
    def add_to_list():
        data = request.get_json()
        team_id = data['team_id']         

        print(f"{team_id} was added to roster")
        return f"{team_id} ", 200
    
    @app.route("/robots/attacked", methods = ["PUT"])
    def notify_attacked():
        data = request.get_json()
        data = data['team_id'] 


        print("a robot was attacked")
        return f"{data} ", 200

if __name__ == "__main__":
    gv = GameViewer()
    gv.run()
