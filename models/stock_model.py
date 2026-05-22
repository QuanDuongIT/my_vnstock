from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class StockData(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    time = db.Column(db.String(50), unique=True)

    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)

    volume = db.Column(db.BigInteger)

    duration = db.Column(db.Integer, default=0)