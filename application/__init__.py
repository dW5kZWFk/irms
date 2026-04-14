from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.automap import automap_base
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_qrcode import QRcode
from logging import FileHandler, WARNING
from logging import WARNING
from flask import render_template, request
from datetime import datetime

file_handler = FileHandler('errorlog.txt')
file_handler.setLevel(WARNING)

db = SQLAlchemy()
Base = automap_base()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
app = Flask(__name__)
qr = QRcode(app)


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    now = datetime.now()
    app.logger.error(f'INTERNAL SERVER ERROR on {request.path}. Time: {now}. Exception: {e}\n')
    return render_template('500.html', now=now), 500


def create_app():

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['JSON_SORT_KEYS'] = False
    #ToDo:
    #SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));

    #TodO: IMPORTANT for deleting multiple values in items
    #SET SESSION group_concat_max_len = 5;

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USERNAME'] = ''
    app.config['MAIL_PASSWORD'] = ''
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_DEFAULT_SENDER'] = 'GTC'

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth_bp.login'
    login_manager.login_message_category = 'info'
    login_manager.login_message = ''

    mail.init_app(app)

    #error handler
    app.logger.addHandler(file_handler)
    app.register_error_handler(404, page_not_found)


    with app.app_context():
        Base.prepare(db.engine, reflect=True)
        from .repair import repair_views
        from .category import category_views
        from .customer import customer_views
        from .home import home_views
        from .inventory import inventory_views
        from .warehouse import warehouse_views
        from .service import service_views
        from .auth import auth_views
        from .purchase_sale import purchase_sale_views
        from .upload import upload_views

        app.register_blueprint(repair_views.repair_bp)
        app.register_blueprint(category_views.category_bp)
        app.register_blueprint(customer_views.customer_bp)
        app.register_blueprint(home_views.home_bp)
        app.register_blueprint(inventory_views.inventory_bp)
        app.register_blueprint(warehouse_views.warehouse_bp)
        app.register_blueprint(service_views.service_bp)
        app.register_blueprint(auth_views.auth_bp)
        app.register_blueprint(purchase_sale_views.purchase_sale_bp)
        app.register_blueprint(upload_views.upload_bp)

        return app
