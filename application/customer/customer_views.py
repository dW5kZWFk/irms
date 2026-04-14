from flask import render_template, redirect, Blueprint, request, jsonify, url_for, flash
from flask_login import login_required
from flask_paginate import Pagination, get_page_parameter
from sqlalchemy import update
from application import db, app
from application.models import customer_table, repair_order_table
from application.customer.customer_func import get_all_customers, add_customer, get_all_customers_by_name
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


customer_bp = Blueprint('customer_bp', __name__, template_folder='templates')


#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@customer_bp.route('/ajax_get_customer_details', methods=['GET'])
def ajax_get_customer_details():
    k_id = request.args.get('k')

    try:
        customer_results = db.session.query(customer_table).filter(customer_table.customer_id == k_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    if customer_results is None:
        return jsonify("empty")

    c_details = {
        "Name:": customer_results.name,
        "E-Mail:": customer_results.email,
        "Telefon:": customer_results.phone_number,
        "Adresse:": customer_results.address
    }

    return jsonify(c_details)


#MAIN+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@customer_bp.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():

    if request.method == "POST":

        if 'delete_button' in request.form:

            try:
                customer_in_order = db.session.query(repair_order_table.id_customer).filter(repair_order_table.id_customer == request.form.get('delete_button'), repair_order_table.state != "abgeschlossen").first()
            except SQLAlchemyError as e:
                flash(f'Der Kundeneintrag konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("customer_bp.customers"))

            if customer_in_order is not None:
                flash("Der Kundeneintrag konnte nicht gelöscht werden, da er in einem offenen Auftrag verwendet wird.", 'danger')
                return redirect(url_for("customer_bp.customers"))

            try:
                db.session.query(customer_table).filter(customer_table.customer_id == request.form.get('delete_button')).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Der Kundeneintrag konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("customer_bp.customers"))

            flash("Der Kundeneintrag wurde gelöscht.", 'success')
            return redirect(url_for("customer_bp.customers"))

        else:
            try:
                add_customer()
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("customer_bp.customers"))
            flash("Der Kundeneintrag wurde hinzugefügt.", 'success')
            return redirect(url_for("customer_bp.customers"))

    per_page = 7
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    if "name" in request.args:
        name = request.args.get("name")
        try:
            customers_content, customers_total = get_all_customers_by_name(name,per_page, offset)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("home_bp.dashboard"))
        if len(customers_content) == 0:
            flash("Es wurde kein Kundeneintrag mit diesem Namen gefunden.", 'info')
            return redirect(url_for("customer_bp.customers"))
        last_name = name
    else:
        try:
            customers_content, customers_total = get_all_customers(per_page, offset)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("home_bp.dashboard"))
        last_name = None

    c_list = []

    for row in customers_content:

            row = list(row)

            try:
                repair_order_results = db.session.query(repair_order_table.repair_order_id)\
                    .filter(repair_order_table.id_customer == row[0], repair_order_table.state != 'abgeschlossen').first()
            except SQLAlchemyError as e:
                flash(f' Die Kunden-Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("home_bp.dashboard"))

            #item is not deletable when it is in an active order

            if repair_order_results:
                row.insert(0, 'yes')
            else:
                row.insert(0, 'no')
            c_list.append(row)

    customers_header = ['Name', 'Email', 'Telefon', 'Adresse']

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(customers_content)} </b>  von <b class=\"bg-white\"> {customers_total} </b>."
    pagination = Pagination(page=page, total=customers_total, per_page=per_page, offset=offset, record_name='Kunden',
                            display_msg=msg, css_framework='bootstrap5')

    return render_template("customers.html", customers=c_list, customers_header=customers_header, pagination=pagination, last_name=last_name)


@customer_bp.route('/customer_edit/<int:c_id>', methods=['GET', 'POST'])
@login_required
def customer_edit(c_id):

    try:
        customer_exists = db.session.query(customer_table.customer_id).filter(customer_table.customer_id == c_id).first()
    except SQLAlchemyError as e:
        flash(f'Der Kunden-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("customer_bp.customers"))

    if not customer_exists:
        flash("Der Kunde existiert nicht.", 'danger')
        return redirect(url_for("customer_bp.customers"))

    if request.method == "POST":

        try:
            stmt = (
                update(customer_table).where(customer_table.customer_id == c_id).values(
                    name=request.form.get('edit_customer_name'),
                    email=request.form.get('edit_customer_email'),
                    phone_number=request.form.get('edit_customer_phone_number'),
                    address=request.form.get('edit_customer_address'))
            )

            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Änderungen konnten nicht gepspeichert werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("customer_bp.customer_edit"))
        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(url_for("customer_bp.customers"))

    try:
        c = db.session.query(customer_table).filter(customer_table.customer_id == c_id).first()
    except SQLAlchemyError as e:
        flash(f' Vorhandene Kundeneinträge konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("customer_bp.customers"))

    c = {
        "Name": c.name,
        "Email": c.email,
        "Telefon": c.phone_number,
        "Adresse": c.address
    }
    return render_template("customer_edit.html", customer=c)
