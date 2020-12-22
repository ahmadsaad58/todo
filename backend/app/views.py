from . import app
from flask_restful import Resource, Api


# create the API
api = Api(app)


# store values in mongo index and each person is a document
