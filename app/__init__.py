from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
migrate = Migrate()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clientes.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    
    from .routes import main
    app.register_blueprint(main)  # Registra o Blueprint com prefixo

    return app