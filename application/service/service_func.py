from flask import request
from application import db, app
from application.models import service_table, repair_order_table
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


def get_single_service(s_id):

    try:
        s = db.session.query(service_table.name, service_table.description, service_table.price).filter(service_table.service_id == s_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f'Fehler in get_single_service (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
    return s


def get_all_services(per_page, offset):

    if per_page == 0 and offset == 0:
        try:
            stmt = f"SELECT service_id, price, name, description from service ORDER BY service_id"
            services_results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f'Fehler in get_all_services (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
        services_total = len(services_results)
    else:
        try:
            stmt = f"SELECT service_id, price, name, description from service ORDER BY service_id LIMIT {per_page} OFFSET {offset}"
            services_results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f'Fehler in get_all_services (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        if services_results is None:
            return None

        try:
            services_total = len(db.session.execute(f"SELECT * from service").fetchall())
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_services (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    service_dict_list = []

    for s in services_results:

        try:
            repair_order_results = db.session.query(repair_order_table.repair_order_id) \
                .filter(repair_order_table.id_service == s.service_id, repair_order_table.state != 'abgeschlossen').first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Die Service-Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        in_order = "no"
        if repair_order_results:
            in_order = "yes"

        price = s.price
        if price:
            price = str(price).replace('.', ',')

        s = {
            "ID": s.service_id,
            "name": s.name,
            "description": s.description,
            "price": price,
            "in_order": in_order
        }

        service_dict_list.append(s)

    return service_dict_list, services_total
