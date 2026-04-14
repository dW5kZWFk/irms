from application import db, app
from application.models import User
from flask import request
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from babel.dates import format_datetime


def get_all_sales(per_page, offset):
    try:
        sales_results = db.session.execute(f"SELECT * FROM sale ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_sales (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if sales_results is None:
        return None
    sale_dict_list = []

    try:
        sales_total = len(db.session.execute("SELECT * FROM sale").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_sales (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    for sale in sales_results:

        price = sale.price
        if price:
            price = str(price).replace('.', ',')

        sale_dict = {
            "ID": sale.sale_id,
            "price": price,
            "date": str(format_datetime(sale.date, locale='de_DE')),
            "description_short": sale.description.split('\n')[0],
            "description": str(sale.description)
        }
        sale_dict_list.append(sale_dict)
    return sale_dict_list, sales_total


def get_all_sales_by_date(date, per_page, offset):
    try:
        sales_results = db.session.execute(f"SELECT * FROM sale WHERE DATE(date) = '{date}' ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_sales_by_date (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if sales_results is None:
        return None


    try:
        sales_total = len(db.session.execute(f"SELECT * FROM sale WHERE DATE(date) = '{date}'").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_sales_by_date (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    sale_dict_list = []
    for sale in sales_results:

        price = sale.price
        if price:
            price = str(price).replace('.', ',')

        sale_dict = {
            "ID": sale.sale_id,
            "price": price,
            "date": str(format_datetime(sale.date, locale='de_DE')),
            "description_short": sale.description.split('\n')[1],
            "description": str(sale.description)
        }
        sale_dict_list.append(sale_dict)
    return sale_dict_list, sales_total


def get_all_sales_by_id(id):
    id = id.replace(" ", "")
    try:
        sales_results = db.session.execute(f"SELECT * FROM sale WHERE sale_id = '{id}'").first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_sales_by_id (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    sale_dict_list = []

    if sales_results is not None:

        price = sales_results.price
        if price:
            price = str(price).replace('.', ',')

        sale_dict = {
            "ID": sales_results.sale_id,
            "price": price,
            "date": str(format_datetime(sales_results.date, locale='de_DE')),
            "description_short": sales_results.description.split('\n')[0],
            "description": str(sales_results.description)
        }
        sale_dict_list.append(sale_dict)

    return sale_dict_list


def get_all_purchases(per_page, offset):

    try:
        purchase_results = db.session.execute(f"SELECT * FROM purchase ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if purchase_results is None:
        return None

    try:
        purchases_total = len(db.session.execute("SELECT * from purchase").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    purchase_dict_list = []

    for purchase in purchase_results:

        try:
            user = User.query.filter_by(user_id=purchase.id_created_by).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_purchases (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        price = purchase.price
        if price:
            price = str(price).replace('.', ',')

        purchase_dict = {
            "ID": purchase.purchase_id,
            "price": price,
            "date": str(format_datetime(purchase.date, locale='de_DE')),
            "created_by": user.username,
            "supplier": str(purchase.supplier),
            "identifier": str(purchase.identifier)
        }
        purchase_dict_list.append(purchase_dict)
    return purchase_dict_list, purchases_total


def get_all_purchases_by_date(date, per_page, offset):

    try:
        purchase_results = db.session.execute(f"SELECT * FROM purchase WHERE DATE(date) = '{date}' ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if purchase_results is None:
        return None

    try:
        purchases_total = len(db.session.execute(f"SELECT * from purchase WHERE DATE(date) = '{date}'").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases_by_date (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    purchase_dict_list = []

    for purchase in purchase_results:

        try:
            user = User.query.filter_by(user_id=purchase.id_created_by).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_purchases_by_date (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        price = purchase.price
        if price:
            price = str(price).replace('.', ',')

        purchase_dict = {
            "ID": purchase.purchase_id,
            "price": price,
            "date": str(format_datetime(purchase.date, locale='de_DE')),
            "created_by": user.username,
            "supplier": str(purchase.supplier),
            "identifier": str(purchase.identifier)
        }
        purchase_dict_list.append(purchase_dict)
    return purchase_dict_list, purchases_total


def get_all_purchases_by_identifier(identifier, per_page, offset):

    identifier = identifier.replace(" ", "")

    try:
        purchase_results = db.session.execute(f"SELECT * FROM purchase WHERE identifier = '{identifier}' ORDER BY UNIX_TIMESTAMP(date) desc LIMIT {per_page} OFFSET {offset}").fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases_by_identifier (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if purchase_results is None:
        return None

    try:
        purchases_total = len(db.session.execute(f"SELECT * from purchase WHERE identifier = '{identifier}'").fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_purchases_by_identifer (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    purchase_dict_list = []

    for purchase in purchase_results:

        try:
            user = User.query.filter_by(user_id=purchase.id_created_by).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_purchases (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        price = purchase.price
        if price:
            price = str(price).replace('.', ',')

        purchase_dict = {
            "ID": purchase.purchase_id,
            "price": price,
            "date": str(format_datetime(purchase.date, locale='de_DE')),
            "created_by": user.username,
            "supplier": str(purchase.supplier),
            "identifier": str(purchase.identifier)
        }
        purchase_dict_list.append(purchase_dict)
    return purchase_dict_list, purchases_total