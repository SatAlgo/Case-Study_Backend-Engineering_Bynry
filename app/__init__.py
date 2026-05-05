"""
StockFlow - B2B Inventory Management Platform
Flask Application Factory
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from app.config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register blueprints
    from app.routes import products_bp, alerts_bp
    app.register_blueprint(products_bp, url_prefix="/api")
    app.register_blueprint(alerts_bp, url_prefix="/api")

    # Register error handlers
    from app.utils.errors import register_error_handlers
    register_error_handlers(app)

    return app
