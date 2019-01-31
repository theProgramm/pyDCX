import json
import os

from flask import Blueprint, request, redirect

import Ultradrive
import app
import mpd

PRESET_PATH = "presets/"


class Presets:
    blue_print: Blueprint
    __ultradrive: Ultradrive

    def __init__(self, logger, ultradrive: Ultradrive):
        self.__logger = logger.getChild("presets")
        self.__preset_files = []
        self.fetch_preset_files()
        self.__http_logger = self.__logger.getChild("http")
        self.__ultradrive: Ultradrive = ultradrive
        self.blue_print = Blueprint('presets', __name__, url_prefix="")
        self.blue_print.add_url_rule("api/preset", view_func=self.preset, methods=["POST"])
        self.blue_print.add_url_rule("/preset", view_func=self.file, methods=["GET"])

    def fetch_preset_files(self):
        for file in os.listdir(PRESET_PATH):
            self.__preset_files.append(file)
            self.__logger.info(f"adding preset: {file}")

    def file(self):
        self.__logger.debug("serving static preset/index.html")
        r = app.app.send_static_file("preset/index.html")
        return r, 200

    def preset(self):
        self.__logger.debug(f"preset args: {request.form.to_dict()}")
        preset = request.form["selection"]
        if preset not in self.__preset_files:
            return "not found", 404

        device: Ultradrive.Device = self.__ultradrive.device(0)
        if device is None:
            return "not available", 401  # FIXME use correct status code

        with open(PRESET_PATH + preset) as f:
            data = json.load(f)
            self.__logger.debug(f"reading preset from file: {preset} got: {data}")
            mpd.set_volume(data["mpd_level"])

        return redirect("/preset")
