import os
import secrets
from PIL import Image
from application import app
from application.models import User
from flask import request
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    try:
        _, f_ext = os.path.splitext(form_picture.filename)
    except Exception as e:
        app.logger.warning(f'OS access exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("Fehler bei Betriebssystem-Zugriff.")

    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    output_size = (125, 125)

    try:
        i = Image.open(form_picture)
    except Exception as e:
        app.logger.warning(f'Image open exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("Das ausgewählt Bild konnte nicht geöffnet werden.")

    i.thumbnail(output_size)

    try:
        i.save(picture_path)
    except Exception as e:
        app.logger.warning(f'Image saving exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("Das Bild konnte nicht gespeichert werden.")

    return picture_fn


def get_all_users():
    try:
        user_results = User.query.filter(User.username != 'deleted_user').all()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim Anzeigen der Benutzer (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    user_dict_list = []
    for user in user_results:

        u = {
            "ID": user.user_id,
            "name": user.username,
            "admin": user.admin_role
        }

        user_dict_list.append(u)
    return user_dict_list
