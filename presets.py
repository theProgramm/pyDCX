import json
import math
import os
from dataclasses import dataclass

from flask import Blueprint, request, redirect

import Ultradrive
import app
import const
import mpd
import protocoll

PRESET_PATH = "presets/"


@dataclass
class Limiter:
    on: bool = False
    threshold: int = 0

    def __init__(self, from_json: dict = None):
        if from_json is not None:
            self.on = bool(from_json["on"])
            self.threshold = min(max(-24, int(from_json["gain"])), 0)


@dataclass
class Output:
    muted: bool
    gain: int
    limiter: Limiter

    def __init__(self, from_json: dict):
        if from_json is None:
            raise ValueError("no data provided")
        self.muted = bool(from_json["muted"])
        self.gain = min(max(-15, int(from_json["gain"])), 15)
        self.limiter = Limiter(from_json["limiter"])


@dataclass
class Preset:
    mpd_volume: int
    main: Output
    sub: Output
    lounge: Output

    def __init__(self, from_json: dict):
        self.mpd_volume = min(max(-1, int(from_json["mpd_level"])), 100)
        self.main = Output(from_json["main"])
        self.sub = Output(from_json["sub"])
        self.lounge = Output(from_json["lounge"])


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
            return "not available", 502

        with open(PRESET_PATH + preset) as f:
            preset_data = Preset(json.load(f))
            self.__logger.debug(f"reading preset from file: {preset} got: {preset_data}")
            mpd_volume = preset_data.mpd_volume
            if mpd_volume > -1:
                mpd.set_volume(mpd_volume)
            self.__ultradrive.write(protocoll.set_muted(0, const.MAIN_LEFT_CHANNEL_ID, preset_data.main.muted))
            self.__ultradrive.write(protocoll.set_muted(0, const.MAIN_RIGHT_CHANNEL_ID, preset_data.main.muted))
            self.__ultradrive.write(protocoll.set_muted(0, const.SUB_CHANNEL_ID, preset_data.sub.muted))
            self.__ultradrive.write(protocoll.set_muted(0, const.MAIN_LEFT_CHANNEL_ID, preset_data.main.muted))

            self.__ultradrive.write(protocoll.set_volume(0, const.MAIN_LEFT_CHANNEL_ID, preset_data.main.gain))
            self.__ultradrive.write(protocoll.set_volume(0, const.MAIN_RIGHT_CHANNEL_ID, preset_data.main.gain))
            self.__ultradrive.write(protocoll.set_volume(0, const.SUB_CHANNEL_ID, preset_data.sub.gain))
            self.__ultradrive.write(protocoll.set_volume(0, const.MAIN_LEFT_CHANNEL_ID, preset_data.main.gain))

        return redirect("/preset")
