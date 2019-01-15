from flask import Flask, send_from_directory
import os
import logging
from api import api
from Ultradrive import Ultadrive

FRONTEND_PATH = "static/duinoDCX_frontend/"

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__, static_url_path="/statics")

app.register_blueprint(api)

static_files = []
ultradrive = Ultadrive


def fetch_frontend_statics():
    app.logger.info("redirecting fro frontend files: ")
    for file in os.listdir(FRONTEND_PATH):
        static_files.append(file)
        app.logger.info(f"walking {file}")


fetch_frontend_statics()
app.logger.info(f"rules: {app.url_map}")


@app.before_first_request
def start_serial():
    ultradrive.start()


@app.route('/<path:path>')
def catch_all(path):
    s = f"requesting: {path}"
    app.logger.info(s)
    if path.split("/")[0] in static_files:
        r = send_from_directory(FRONTEND_PATH, path)
        return r, 201
    return s, 204


if __name__ == '__main__':
    app.run()
