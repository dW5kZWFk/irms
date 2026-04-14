from flask import request
from application import app, db
from application.models import warehouse_table, item_table
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


def check_warehouse_entry_deleted(w_id):
    try:
        warehouse_results = db.session.query(warehouse_table.warehouse_id).filter(
            warehouse_table.warehouse_id == w_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Prüfen der Lager-Eintrag Verfügbarkeit fehlgehschlagen. {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if warehouse_results is None:
        return True
    return False


#used for product_edit
def get_warehouse_box_numbers():
    try:
        box_numbers = [w.box_number for w in db.session.query(warehouse_table.box_number).distinct()]
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim Laden der Lager Fach-IDs (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
    return box_numbers


#all already set shelf numbers -> distinct
def get_shelf_numbers():
    try:
        shelf_numbers = [w.shelf_number for w in db.session.query(warehouse_table.shelf_number).distinct()]
    except Exception as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim Laden der Lager Schrank-IDs (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
    return shelf_numbers


def get_warehouse_content():

    try:
        warehouse_content = db.session.execute('''SELECT warehouse_id, shelf_number,
                            compart_number, box_number, description from warehouse;''').fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim Laden vorhandener Lager Einträge (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    w_list = []
    #find out whether category is part of none sold item
    for row in warehouse_content:
        row = list(row)

        try:
            item_results = db.session.query(item_table.item_id) \
                .filter(item_table.id_warehouse == row[0], item_table.id_sale == None).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Die Lager-Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        #category is not deletable when it is in an active item
        if item_results:
            row.insert(0, 'yes')
        else:
            row.insert(0, 'no')

        w_list.append(row)

    return w_list


def get_values_from_warehouse_form():

    s_number = request.form.get("warehouse_shelf_number")
    if s_number == 'neu' or s_number is None:
        s_number = request.form.get("warehouse_shelf_number_new")

    c_number = request.form.get("warehouse_compart_number")
    if c_number == 'neu' or c_number is None:
        c_number = request.form.get("warehouse_compart_number_new")

    b_number = request.form.get("warehouse_box_number")

    return s_number, c_number, b_number
