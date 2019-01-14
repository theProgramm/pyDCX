from flask.views import View, MethodView
from flask import Blueprint

api = Blueprint('api', __name__, url_prefix="/api")


@api.route("/devices")
def catch_all():
    return "", 201
