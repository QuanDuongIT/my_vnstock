import os

if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

from flask import Flask
from config import DATABASE_URL
from models.stock_model import db
from routes.stock_routes import stock_bp

from services.stock_worker import start_worker, init_scanner


def create_app():

    app = Flask(__name__)

    # load config FIRST
    app.config.from_object("config")

    # override DB nếu cần
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "sslmode": "require"
        }
    }

    # init db
    db.init_app(app)

    # register blueprint
    app.register_blueprint(stock_bp)

    # create tables
    with app.app_context():
        db.create_all()

    # init scanner + worker (SAU KHI config đã load)
    with app.app_context():
        init_scanner(app.config["VNSTOCK_API_KEY"])
        start_worker()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=True,
        use_reloader=False
    )