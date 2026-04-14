import os

from flask import render_template, redirect, request, jsonify, Blueprint, url_for, flash, session
from flask_login import current_user
from flask_paginate import Pagination, get_page_parameter
from application import db, app
from application.inventory.inventory_func import set_upload_id_null
from application.models import online_upload_table, item_table
from application.upload.upload_func import get_upload_dict, get_upload_dict_by_id, check_for_completed_orders
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


upload_bp = Blueprint('upload_bp', __name__, template_folder = 'templates', url_prefix='')


@upload_bp.route('/upload_name_search_ajax', methods=['GET'])
def upload_name_search_ajax():

    search_value = request.args.get("search_val")

    if search_value is not None:
        try:
            uploads = db.session.query(online_upload_table.online_upload_id, online_upload_table.name).filter(
                online_upload_table.name.ilike('%' + search_value + '%'), online_upload_table.id_shop_order == None).all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (upload_name_search_ajax). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        if len(uploads) == 0:
            return jsonify("empty")
        else:
            uploads_dict_list = []
            for u in uploads:
                u_dict = {
                    "id": u.online_upload_id,
                    "name": u.name
                }
                uploads_dict_list.append(u_dict)
            return jsonify(uploads_dict_list)
    return jsonify("empty")


@upload_bp.route('/upload_id_search_ajax', methods=['GET'])
def upload_id_search_ajax():

    search_value = request.args.get("id")
    search_value = search_value.replace(" ", "")
    if search_value is not None:
        try:
            uploads = db.session.query(online_upload_table.online_upload_id, online_upload_table.name).filter(
                online_upload_table.online_upload_id.ilike(search_value)).all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (upload_name_search_ajax). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        if len(uploads) == 0:
            return jsonify("empty")
        else:
            uploads_dict_list = []
            for u in uploads:
                u_dict = {
                    "id": u.online_upload_id,
                    "name": u.name
                }
                uploads_dict_list.append(u_dict)
            return jsonify(uploads_dict_list)
    return jsonify("empty")


@upload_bp.route('/upload_management', methods=['GET', 'POST'])
def upload_management():
    if current_user.admin_role != 1:
        return render_template("restricted.html")

    try:
        check_for_completed_orders()
    except Exception as e:
        flash(f"{str(e)}", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    if request.method == "POST":
        if "delete_button" in request.form:

            u_id = request.form.get("delete_button")

            try:
                upload_results = db.session.query(online_upload_table.id_shop_order).filter(
                    online_upload_table.online_upload_id == u_id).first()
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Fehler beim Löschen des Uploads. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}",
                    'danger')
                return redirect(url_for("upload_bp.upload_management"))


            if upload_results.id_shop_order is not None:
                flash(f"Der Upload ist Teil einer Bestellung und kann derzeit nicht gelöscht werden.", 'danger')
                return redirect(url_for("upload_bp.upload_management"))


            #query all items:
            try:
                item_ids = [r.item_id for r in
                                    db.session.query(item_table.item_id).filter(
                                        item_table.id_online_upload == u_id)]
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash("Fehler beim Löschen des Uploads. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}",
                    'danger')
                return redirect(url_for("upload_bp.upload_management"))

            if item_ids is not None and item_ids:
                for i in item_ids:
                    try:
                        set_upload_id_null(i)
                    except Exception as e:
                        flash(f"Fehler beim Löschen des Uploads. {str(e)}", 'danger')
                        return redirect(url_for("upload_bp.upload_management"))

                try:
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    app.logger.warning(f'SQLAlchemy commit failed (change id_online_uplaod for items)  on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    flash(f"Fehler beim Löschen des Uploads. {str(e)}", 'danger')
                    return redirect(url_for("upload_bp.upload_management"))


            try:
                db.session.query(online_upload_table).filter(online_upload_table.online_upload_id == u_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Fehler beim Löschen des Uploads. (Items wurden dem Inventar wieder hinzugefügt, falls welche vorhanden waren.)", 'danger')
                return redirect(url_for("upload_bp.upload_management"))

            import shutil
            try:
                picture_directory_path = os.path.join(app.root_path, 'static/noporn/', 'upload_' + str(u_id))
                if os.path.exists(picture_directory_path) is True:
                    shutil.rmtree(picture_directory_path, ignore_errors=True)
            except FileExistsError as f:
                raise Exception(f'Fehler beim Löschen des Upload Bild-Ordners upload_{str(u_id)}.{str(f)}')

            flash("Der Upload wurde entfernt und Items, falls vorhanden, wieder dem Inventar hinzugefügt.", 'success')
            return redirect(url_for("upload_bp.upload_management"))


    if "id" in request.args:
        id = request.args.get("id")

        if id == '':
            return redirect(url_for("upload_bp.upload_management"))
        upload_dict_list = get_upload_dict_by_id(id)

        if len(upload_dict_list) == 0:
            flash("Es wurde kein Upload mit dieser ID gefunden.", 'info')
            return redirect(url_for("upload_bp.upload_management"))

        return render_template("upload_management.html", uploads=upload_dict_list, last_id = id)

    if "item_id" in request.args:
        item_id = request.args.get("item_id")

        if item_id == '':
            return redirect(url_for("upload_bp.upload_management"))

        item_id = item_id.replace(" ", "")
        try:
            upload_id = db.session.query(online_upload_table.online_upload_id).join(item_table).filter(item_table.item_id == item_id).first()
        except SQLAlchemyError as e:
            flash(f'Fehler bei der Suche nach Uplaods. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("upload_bp.upload_management"))

        if upload_id is not None:
            upload_dict_list = get_upload_dict_by_id(upload_id.online_upload_id)
        else:
            flash("Das Item wurde in keinem der Uploads gefunden.", 'info')
            return redirect(url_for("upload_bp.upload_management"))

        if len(upload_dict_list) == 0:
            flash("Es wurde ein Upload mit diesem Item gefunden, jedoch kein Upload mit der ID. Logik Fehler, oder der Upload wurde zwischenzeitlich entfernt.", 'danger')
            return redirect(url_for("upload_bp.upload_management"))

        return render_template("upload_management.html", uploads=upload_dict_list, last_item_id = item_id)

    per_page = 7
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        upload_dict_list, uploads_total = get_upload_dict(per_page, offset)
    except Exception as e:
        flash(f"Fehler beim Laden der Uploads. {str(e)}", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(upload_dict_list)} </b>  von <b class=\"bg-white\"> {uploads_total} </b>."
    pagination = Pagination(page=page, total=uploads_total, per_page=per_page, offset=offset, record_name='Uploads',
                            display_msg=msg, css_framework='bootstrap5', show_single_page=False)

    return render_template("upload_management.html", uploads=upload_dict_list, pagination=pagination)


@upload_bp.route('/upload_edit/<int:u_id>', methods=['GET', 'POST'])
def upload_edit(u_id):

    try:
        upload_exists = db.session.query(online_upload_table.online_upload_id, online_upload_table.id_shop_order).filter(online_upload_table.online_upload_id == u_id).first()
    except SQLAlchemyError as e:
        flash(f' Upload-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("upload_bp.upload_management"))

    if not upload_exists:
        flash("Der Upload-Eintrag existiert nicht mehr.", 'danger')
        return redirect(url_for("upload_bp.upload_management"))

    if upload_exists.id_shop_order is not None:
        flash("Der Upload ist Teil einer Bestellung und kann derzeit nicht bearbeitet werden.", 'danger')
        return redirect(url_for("upload_bp.upload_management"))

    if request.method == "POST":
        if request.form.get("edit_upload") is not None:
            try:
                stmt = update(online_upload_table).where(online_upload_table.online_upload_id == u_id).values(
                    name=request.form.get('new_upload_name'), description=request.form.get("new_upload_description"),
                    price=request.form.get("new_upload_price").replace(',', '.'))
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for('upload_bp.upload_management'))
            flash('Änderungen wurden gespeichert.', 'success')
            return redirect(url_for('upload_bp.upload_management'))

    try:
        u = db.session.query(online_upload_table).filter(online_upload_table.online_upload_id == u_id).first()
    except SQLAlchemyError as e:
        flash(f' Upload-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("upload_bp.upload_management"))

    price = u.price
    if price:
        price = str(price).replace('.', ',')

    u_dict = {
        "name": u.name,
        "description": u.description,
        "price": price
    }

    return render_template("upload_edit.html", upload=u_dict)