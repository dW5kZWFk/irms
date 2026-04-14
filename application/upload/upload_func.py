from flask import request
from application import db, app
from application.models import online_upload_table, item_table, shop_order_table, sale_table
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import update
from babel.dates import format_datetime
from datetime import datetime, date
import os


def add_upload_to_sale(u_id):
    from application.inventory.inventory_func import get_single_item_description, set_sale_id_item

    try:
        upload_order_results = db.session.query(shop_order_table.date_completed,online_upload_table.price, online_upload_table.name, online_upload_table.description).\
            join(shop_order_table).filter(online_upload_table.online_upload_id == u_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception in "add_upload_to_sale" on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(e)

    description = "Abgeschlossener Online Verkauf \n ID:" + str(u_id) + ', Completed Datum: ' + str(
        upload_order_results.date_completed) + '\n\n'
    description += "Upload Bezeichnung: " + str(upload_order_results.name) + '\n'
    description += "Upload Beschreibung: " + str(upload_order_results.description) + '\n\n'

    try:
        id_list = [r.item_id for r in db.session.query(item_table.item_id)
                .filter(item_table.id_online_upload == u_id).all()]
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception in "add_upload_to_sale" on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(e)

    if len(id_list) == 1:
        description += "Verkauftes Item:" + '\n'
    else:
        description += "Verkaufte Items:" + '\n'

    for i in id_list:
        try:
            description_item = get_single_item_description(i)
        except Exception as e:
            raise Exception(e)
        description += description_item

    description += '----------------------------------\n'
    description += "Gesamtpreis: " + str(upload_order_results.price).replace('.', ',') + ' €'

    s = sale_table(price=upload_order_results.price, description=description, id_created_by=1)

    db.session.add(s)
    db.session.flush()
    sa_id = s.sale_id

    for i in id_list:
        try:
            set_sale_id_item(i, sa_id)
        except Exception as e:
            raise Exception(e)

    try:
        stmt = update(online_upload_table).where(online_upload_table.online_upload_id == u_id).values(id_sale=sa_id)
        db.session.execute(stmt)
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in add_uplaod_to_sale (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}')

    import shutil
    try:
        picture_directory_path = os.path.join(app.root_path, 'static/noporn/', 'upload_'+str(u_id))
        if os.path.exists(picture_directory_path) is True:
            shutil.rmtree(picture_directory_path, ignore_errors=True)
    except FileExistsError as f:
        raise Exception(f'Fehler beim Löschen des Upload Bild-Ordners upload_{str(u_id)}.{str(f)}')

    return None


def check_for_completed_orders():
    try:
        completed_orders =  db.session.query(online_upload_table.online_upload_id, shop_order_table.date_completed)\
            .join(online_upload_table).filter(shop_order_table.state == 'completed', online_upload_table.id_sale == None).all()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception in "check_for_completed_orders" on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in "check_for_completed_orders". {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    for c in completed_orders:
        days_after_completion = (date.today() - c.date_completed.date()).days

        if days_after_completion > 14:
           try:
               add_upload_to_sale(c.online_upload_id)
               db.session.commit()
           except Exception as e:
               db.session.rollback()
               raise Exception(f"Abgeschlossener Auftrag {c.online_upload_id} konnte den Verkäufen nicht hinzugefügt werden. {str(e)}")


    return None


def check_upload_availability(u_id):

    try:
        upload_results = db.session.query(online_upload_table).where(online_upload_table.online_upload_id == u_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in "check_upload_availability". {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if upload_results is None:
        return True
    #toDo check upload state (in order / sold etc)
    return False


def add_upload():
    try:
        u = online_upload_table(name=request.form.get('new_upload_name'), price=request.form.get('new_upload_price').replace(',', '.'), description=request.form.get('new_upload_description'), date=datetime.now())
        db.session.add(u)
        db.session.flush()
        u_id = u.online_upload_id
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f"Fehler in 'add upload'. {str(e)} (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}")

    try:
        picture_directory_path = os.path.join(app.root_path, 'static/noporn/', 'upload_'+str(u_id))
        os.mkdir(picture_directory_path)
    except FileExistsError as f:
        raise Exception(f'Fehler beim Erstellen des Ordners für die Bilder. {str(f)}')

    return u_id


def get_upload_dict(per_page, offset):

    #date => hinzugefügt am
    try:
        upload_results = db.session.execute(f"SELECT * FROM online_upload WHERE id_sale IS NULL ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_upload_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if upload_results is None:
        return None

    try:
        uploads_total = len(db.session.execute(f"SELECT * FROM online_upload WHERE id_sale IS NULL; ").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_upload_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    uploads_dict_list = []

    for upload in upload_results:

        price = upload.price
        if price:
            price = str(price).replace('.', ',')

        try:
            item_results = db.session.query(item_table.item_id).filter(item_table.id_online_upload == upload.online_upload_id).all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_upload_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        if item_results is None:
            number_items = 0
        else:
            number_items = len(item_results)

        upload_dict = {
            "ID": upload.online_upload_id,
            "name": upload.name,
            "price": price,
            "description": str(upload.description),
            "date": str(format_datetime(upload.date, locale='de_DE')),
            "number_items": number_items,
            "id_shop_order": upload.id_shop_order
        }
        uploads_dict_list.append(upload_dict)
    return uploads_dict_list, uploads_total


def get_upload_dict_by_id(id):
    if (isinstance(id, str)):
        id = id.replace(" ", "")

    #date => hinzugefügt am
    try:
        upload_results = db.session.execute(f"SELECT * FROM online_upload WHERE id_sale IS NULL AND online_upload_id = '{id}'").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_upload_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if upload_results is None:
        return None

    uploads_dict_list = []

    for upload in upload_results:

        price = upload.price
        if price:
            price = str(price).replace('.', ',')

        try:
            item_results = db.session.query(item_table.item_id).filter(item_table.id_online_upload == upload.online_upload_id).all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_upload_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        if item_results is None:
            number_items = 0
        else:
            number_items = len(item_results)

        upload_dict = {
            "ID": upload.online_upload_id,
            "name": upload.name,
            "price": price,
            "description": str(upload.description),
            "date": str(format_datetime(upload.date, locale='de_DE')),
            "number_items": number_items,
            "id_shop_order": upload.id_shop_order
        }
        uploads_dict_list.append(upload_dict)
    return uploads_dict_list
