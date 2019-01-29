import time
from threading import RLock

import flask
from flask import Blueprint
from flask import request

import Ultradrive


class Api:
    api: Blueprint
    __ultradrive: Ultradrive
    lock: RLock = RLock()

    def __init__(self, logger, ultradrive: Ultradrive):
        self.__logger = logger.getChild("api")
        self.__http_logger = self.__logger.getChild("http")
        self.__ultradrive = ultradrive
        self.api = Blueprint('api', __name__, url_prefix="/api")
        self.api.add_url_rule("/devices", view_func=self.devices)
        self.api.add_url_rule("/devices/<int:n>", view_func=self.device)
        self.api.add_url_rule("/commands", view_func=self.commands, methods=["POST"])

    def devices(self):
        ret = bytearray()
        for n, d in self.__ultradrive.devices().items():
            if d.last_pong is not None:
                ret.extend(d.search_response)
        self.__http_logger.debug(f"devies -> {ret}")
        return flask.make_response(ret)

    def device(self, n: int):
        with self.lock:
            try:
                s = self.__ultradrive.device(n).to_gui()
            except KeyError as e:
                return "not found", 404
            self.__http_logger.debug(f"device({n}) -> {s}")
            return flask.make_response(s)

    def commands(self):
        with self.lock:
            self.__http_logger.info(f"commands: {request} data: {request.data}")
            device_id = self.__ultradrive.process_outgoing(request.data)
            while self.__ultradrive.devices()[device_id].invalidate_sync:
                time.sleep(0.0001)
            return "", 204
