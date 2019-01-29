import logging
import os

from flask import Flask, send_from_directory, request

from Ultradrive import Ultadrive
from api import Api
from const import FRONTEND_PATH


class Data:
    def __init__(self):
        self.static_files = []
        logging.getLogger('apscheduler').setLevel(logging.INFO)
        logging.getLogger('flask').setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('flask.app.').setLevel(logging.ERROR)
        logging.getLogger('flask.app.api.http').setLevel(logging.INFO)
        logging.getLogger('flask.app.ultradrive').setLevel(logging.INFO)
        logging.getLogger('flask.app.ultradrive.io').setLevel(logging.INFO)
        logging.getLogger('flask.app.ultradrive.packet').setLevel(logging.INFO)
        logging.getLogger('flask.app.ultradrive.protocol').setLevel(logging.INFO)

        self.fetch_frontend_statics()

        self.ultradrive = Ultadrive(app.logger)
        self.__api = Api(app.logger, self.ultradrive)

        self.start_serial()

        app.register_blueprint(self.__api.api)
        app.logger.info(f"rules: {app.url_map}")

    def fetch_frontend_statics(self):
        app.logger.info("redirecting fro frontend files: ")

        for file in os.listdir(FRONTEND_PATH):
            self.static_files.append(file)
            app.logger.info(f"walking {file}")

    def start_serial(self):
        self.ultradrive.start()


app = Flask(__name__, static_url_path="/statics")
data = None


@app.before_first_request
def setup():
    global data
    if data is None:
        data = Data()


@app.route('/<path:path>', methods=["GET", "HEAD", "OPTIONS", "POST"])
def catch_all(path):
    if path.split("/")[0] in data.static_files:
        r = send_from_directory(FRONTEND_PATH, path)
        return r, 201
    s = f"fall through: {request} - {request.args.to_dict()}"
    app.logger.info(s)
    return f"fall through: {path}", 204


if __name__ == '__main__':
    print("lets go!")
    app.run(host="0.0.0.0", port=5000, debug=True)
