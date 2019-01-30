from datetime import datetime

import flask
from flask import Blueprint
from flask import request

import Ultradrive


class Api:
    api: Blueprint
    __ultradrive: Ultradrive

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
        now = datetime.now()
        for n, d in self.__ultradrive.devices().items():
            if d.is_active(now):
                ret.extend(d.search_response)
        self.__http_logger.debug(f"devies -> {ret}")
        return flask.make_response(ret)

    def device(self, n: int):
        try:
            s = self.__ultradrive.device(n).to_gui()
        except KeyError as e:
            return "not found", 404
        self.__http_logger.debug(f"device({n}) -> {s}")
        return flask.make_response(s)

    def commands(self):
        self.__http_logger.info(f"commands: {request} data: {request.data}")
        self.__ultradrive.process_outgoing(request.data)
        return "", 204
