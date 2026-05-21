from flask import Flask
from config import DATABASE_URL

from models.stock_model import db
from routes.stock_routes import stock_bp

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config.from_object("config")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "sslmode": "require"
    }
}

db.init_app(app)

app.register_blueprint(stock_bp)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(
        debug=True,
        use_reloader=False
    )