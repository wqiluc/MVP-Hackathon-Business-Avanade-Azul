from flask import Flask
from flask_cors import CORS

from app.config.settings import Config
# from app.extensions import db

def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    CORS(app, 
        resources={
            r"/api/*": {
                "origins": "*"
                }
            }
        )
    # db.init_app(app)

    return app