import json

from flask import render_template, Blueprint, url_for, request, redirect, jsonify, flash
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_parameter
from application.models import service_table, repair_order_table
from application.service.service_func import get_all_services
from application import db, app
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os


service_bp = Blueprint('service_bp', __name__, template_folder='templates')


#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@service_bp.route('/ajax_get_service_details', methods=['GET'])
def ajax_get_service_details():

    s_id = request.args.get('service_id')

    #toDo: testen ob die abfrage notwendig ist
    if s_id == '-':
        return jsonify("empty")

    try:
        service_results = db.session.query(service_table).filter(service_table.service_id == s_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    if service_results is None:
        return jsonify("empty")

    price = service_results.price
    if price:
        price = str(price).replace('.', ',')

    s_details = {
        "Name:": service_results.name,
        "Beschreibung:": service_results.description,
        "Preis:": price
    }

    return jsonify(s_details)


@service_bp.route('/ajax_service_search', methods=['GET'])
def ajax_service_search():
    search_value_name = request.args.get('search_value_name')

    try:
        services_results = db.session.query(service_table.service_id, service_table.price, service_table.name,
                                service_table.description).filter(service_table.name.ilike('%' + search_value_name + '%')).all()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    if len(services_results) == 0:
        return jsonify("empty")

    service_dict_list = []

    for s in services_results:

        try:
            repair_order_results = db.session.query(repair_order_table.repair_order_id) \
                .filter(repair_order_table.id_service == s.service_id, repair_order_table.state != 'abgeschlossen').first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        in_order = "no"
        if repair_order_results:
            in_order = "yes"

        s_dict = {
            "ID": s.service_id,
            "name": s.name,
            "description": s.description,
            "price": s.price,
            "in_order": in_order
        }
        service_dict_list.append(s_dict)

    return jsonify(service_dict_list)


#MAIN+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@service_bp.route('/services', methods=['GET', 'POST'])
@login_required
def services():

    if request.method == "POST":
        if request.form.get("delete_button") is not None:

            try:
                repair_order_results = db.session.query(repair_order_table.repair_order_id) \
                    .filter(repair_order_table.id_service == request.form.get("delete_button"),
                            repair_order_table.state != 'abgeschlossen').first()
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash("Fehler beim Löschen des Services. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                return redirect(url_for("service_bp.services"))

            if repair_order_results is not None:
                flash("Der Service konnte nicht gelöscht werden, da er Teil eines offenen Auftrages ist.", 'danger')
                return redirect(url_for("service_bp.services"))

            try:
                db.session.query(service_table).filter(service_table.service_id == request.form.get("delete_button")).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Service konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("service_bp.services"))
            flash("Der Service wurde gelöscht.", 'success')
            return redirect(url_for("service_bp.services"))

        if request.form.get("add_service") is not None:
            try:
                s = service_table(name=request.form.get("new_service_name"), description=request.form.get("new_service_description"),
                                  price=request.form.get("new_service_price").replace(',', '.'))
                db.session.add(s)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Service konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("service_bp.services"))
            flash("Service wurde hinzugefügt.", 'success')
            return redirect(url_for("service_bp.services"))

    per_page = 7
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        service_dict_list, services_total = get_all_services(per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(service_dict_list)} </b>  von <b class=\"bg-white\"> {services_total} </b>."
    pagination = Pagination(page=page, total=services_total, per_page=per_page, offset=offset, record_name='Services',
                            display_msg=msg, css_framework='bootstrap5')

    return render_template("services.html", services=service_dict_list, pagination=pagination)


@service_bp.route('/service_edit/<int:s_id>', methods=['GET', 'POST'])
@login_required
def service_edit(s_id):

    try:
        service_exists = db.session.query(service_table.service_id).filter(service_table.service_id == s_id).first()
    except SQLAlchemyError as e:
        flash(f' Service Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("service_bp.services"))

    if not service_exists:
        flash("Der Service existiert nicht.", 'danger')
        return redirect(url_for("service_bp.services"))

    if request.method == "POST":
        if request.form.get("edit_service") is not None:
            try:
                stmt = update(service_table).where(service_table.service_id == s_id).values(
                    name=request.form.get('new_service_name'), description=request.form.get("new_service_description"),
                    price=request.form.get("new_service_price").replace(',', '.'))
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for('service_bp.services'))
            flash('Änderungen wurden gespeichert.', 'success')
            return redirect(url_for('service_bp.services'))

    try:
        s = db.session.query(service_table).filter(service_table.service_id == s_id).first()
    except SQLAlchemyError as e:
        flash(f' Service Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("service_bp.services"))

    price = s.price
    if price:
        price = str(price).replace('.', ',')
    s_dict = {
        "name": s.name,
        "description": s.description,
        "price": price
    }

    return render_template("service_edit.html", service=s_dict)


@service_bp.route('/automatic_mail', methods=['GET', 'POST'])
@login_required
def automatic_mail():
    if current_user.admin_role != 1:
        return render_template("restricted.html")

    file_path = os.path.join(app.root_path, 'static/mail_content.txt')

    if request.method == "POST":
        new_mail_content = request.form.get("new_mail_content")

        try:
            with open(file_path, 'w') as f:
                f.write(new_mail_content)
        except Exception as e:
            app.logger.warning(f'OS file write exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            flash("Änderungen konnten nicht in Datei geschrieben werden.", 'danger')
            return redirect(url_for('service_bp.automatic_mail'))

        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(url_for('service_bp.automatic_mail'))

    try:
        f = open(file_path, "r")
        email_content = f.read()
        f.close()
    except Exception as e:
        app.logger.warning(f'OS file read exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash("Datei konnte nicht geladen werden.", 'danger')
        return redirect(url_for('home_bp.dashboard'))

    text = email_content.split('\n')

    return render_template("automatic_mail.html", mail_content_split=text, mail_content=email_content)


@service_bp.route('/contact_info', methods=['GET', 'POST'])
@login_required
def contact_info():
    file = os.path.join(app.root_path, 'static/contact_info.json')

    if request.method=="POST":
        contact_inf = {
            'address': request.form.get("address"),
            'mail': request.form.get("mail"),
            'phone': request.form.get("phone"),
            'legal_general': request.form.get("legal_general")
        }

        try:
            with open(file, 'w') as json_file:
                json.dump(contact_inf, json_file)
        except Exception as e:
            app.logger.warning(f'OS file write exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            flash("Änderungen konnten nicht in Datei geschrieben werden.", 'danger')
            return redirect(url_for('service_bp.contact_info'))

    try:
        with open(file, 'r') as json_file:
            data = json.loads(json_file.read())
    except Exception as e:
        app.logger.warning(f'OS file read exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash("Datei konnte nicht geladen werden.", 'danger')
        return redirect(url_for('home_bp.dashboard'))


    return render_template("contact_info.html", contact_info=data)