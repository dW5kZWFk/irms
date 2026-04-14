from application import db, app
from application.models import customer_table, repair_order_table
from flask import request
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

def get_all_customers(per_page, offset):
    if per_page == 0 and offset == 0:

        try:
            customers = db.session.execute(f'''SELECT customer.customer_id, customer.name, customer.email, customer.phone_number, customer.address FROM customer
                                         ORDER BY customer_id''').fetchall()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(
                f' Fehler in get_all_customers. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
        customers_total = len(customers)
    else:

        try:
            customers = db.session.execute(f'''SELECT customer.customer_id, customer.name, customer.email, customer.phone_number, customer.address FROM customer
                                         ORDER BY customer_id DESC LIMIT {per_page} OFFSET {offset}''').fetchall()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_customers. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        try:
            customers_total = len(db.session.execute(f'''SELECT * from customer;''').fetchall())
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_all_customers. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return customers, customers_total


def get_all_customers_by_name(name, per_page, offset):
    name = name.lower()
    name = name.replace(" ", "")

    try:
        customers = db.session.execute(f'''SELECT customer.customer_id, customer.name, customer.email, customer.phone_number, customer.address FROM customer 
                                            WHERE LOWER(REPLACE(customer.name, ' ', '')) LIKE '%{name}%'
                                     ORDER BY customer_id DESC LIMIT {per_page} OFFSET {offset}''').fetchall()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_customers_by_name. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    try:
        customers_total = len(db.session.execute(f'''SELECT * from customer WHERE LOWER(REPLACE(customer.name, ' ', '')) LIKE '%{name}%';''').fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_all_customers_by_name. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return customers, customers_total


def get_single_customer_name(c_id):
    try:
        c = db.session.execute(f'''SELECT customer_id, name
                              FROM customer WHERE customer_id={c_id};''').one()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_single_customer_name. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return c


def add_customer():
    name_customer = request.form.get('new_customer_prename')+' '+request.form.get('new_customer_surname')

    try:
        c = customer_table(name=name_customer,
                 email=request.form.get('new_customer_email'),
                 phone_number=request.form.get('new_customer_phone_number'),
                 address=request.form.get('new_customer_address'))

        db.session.add(c)
        db.session.commit()
    except SQLAlchemyError as e:
        raise Exception(f' Fehler beim Hinzufügen des Kundens. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}')

    return c.customer_id
