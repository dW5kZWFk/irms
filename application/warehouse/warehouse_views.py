from flask import render_template, request, jsonify, Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from application import db, app
from application.models import warehouse_table, item_table
from application.warehouse.warehouse_func import get_warehouse_box_numbers, get_shelf_numbers, get_values_from_warehouse_form, get_warehouse_content
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

warehouse_bp = Blueprint('warehouse_bp', __name__, template_folder='templates', url_prefix='')


#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


#used for input_values and product_edit
@warehouse_bp.route('/get_warehouse_box_numbers_ajax', methods=['GET'])
@login_required
def get_warehouse_box_numbers_ajax():
    try:
        box_numbers = get_warehouse_box_numbers()
    except Exception:
        return jsonify("error")

    return jsonify(box_numbers)


@warehouse_bp.route('/warehouse_ajax_response', methods=['GET'])
def warehouse_ajax_response():

    if request.args.get('go') is not None:
        try:
            shelf_numbers = get_shelf_numbers()
        except Exception as e:
            return jsonify("error")

        return jsonify(shelf_numbers)

    if request.args.get('shelf_number') is not None:
        try:
            compart_numbers = [w.compart_number for w in
                       db.session.query(warehouse_table.compart_number).filter(
                           warehouse_table.shelf_number == request.args.get('shelf_number')).distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        return jsonify(compart_numbers)

    return jsonify("empty")


#MAIN+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@warehouse_bp.route('/warehouse_management', methods=['GET', 'POST'])
@login_required
def warehouse_management():
    if current_user.admin_role != 1:
        return render_template("restricted.html")

    warehouse_header = ["ID", "Schrank-ID", "Fach-ID", "Kiste-ID", "Beschreibung"]

    if request.method == "POST":

        #delete warehouse entry
        if 'delete_button' in request.form:

            try:
                warehouse_entry_used = db.session.query(item_table.item_id).filter(item_table.id_warehouse == request.form.get('delete_button'), item_table.id_sale == None).first()
            except SQLAlchemyError as e:
                flash(f'Lager-Eintrag konnte nicht gelöscht werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("warehouse_bp.warehouse_management"))

            if warehouse_entry_used is not None:
                flash("Der Lager-Eintrag konnte nicht gelöscht werden, da er verwendet wird.", 'danger')
                return redirect(url_for("warehouse_bp.warehouse_management"))

            try:
                db.session.query(warehouse_table).filter(
                    warehouse_table.warehouse_id == request.form.get('delete_button')).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Lager-Eintrag konnte nicht entfernt werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("warehouse_bp.warehouse_management"))

            flash("Lager-Eintrag wurde entfernt.", 'success')
            return redirect(url_for("warehouse_bp.warehouse_management"))

        #add new warehouse entry
        s_number, c_number, b_number = get_values_from_warehouse_form()

        if b_number == '':
            flash("Das Feld 'Kisten-ID' darf nicht leer sein.", 'danger')
            return redirect(url_for("warehouse_bp.warehouse_management"))

        #check whether box number already exists
        try:
            existing_box_number = db.session.query(warehouse_table.box_number).filter(warehouse_table.box_number == b_number).first()
        except SQLAlchemyError as e:
            flash(f' Lager-Eintrag konnte nicht hinzugefügt werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("warehouse_bp.warehouse_management"))

        if existing_box_number is not None:
            flash("Die angegebene Kisten-ID wird bereits verwendet.", 'danger')
            return redirect(url_for("warehouse_bp.warehouse_management"))

        try:
            w = warehouse_table(shelf_number=s_number, compart_number=c_number, box_number=b_number,
                                description=request.form.get("warehouse_description"))
            db.session.add(w)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Lager-Eintrag konnte nicht hinzugefüt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("warehouse_bp.warehouse_management"))

        flash("Lager-Eintrag wurde hinzugefügt.", 'success')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    #fetch existing entries
    try:
        warehouse_content = get_warehouse_content()
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    return render_template("warehouse_management.html", warehouse_header=warehouse_header,
                           warehouse_content=warehouse_content)


@warehouse_bp.route('/warehouse_edit/<int:w_id>', methods=['GET', 'POST'])
@login_required
def warehouse_edit(w_id):
    if current_user.admin_role != 1:
        return render_template("restricted.html")

    try:
        warehouse_entry_exists = db.session.query(warehouse_table.warehouse_id).filter(warehouse_table.warehouse_id == w_id).first()
    except SQLAlchemyError as e:
        flash(f'Lager-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    if warehouse_entry_exists is None:
        flash("Der Lager-Eintrag existiert nicht.", 'danger')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    try:
        w = db.session.query(warehouse_table).filter(warehouse_table.warehouse_id == w_id).first()
    except SQLAlchemyError as e:
        flash(f' Lager-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect("warehouse_bp.warehouse_management")

    if request.method == "POST":

        s_number, c_number, b_number = get_values_from_warehouse_form()

        if b_number == '':
            flash("Das Feld 'Kisten-ID' darf nicht leer sein.")
            return redirect(url_for("warehouse_bp.warehouse_edit", w_id=w_id))

        #existieren Kisten-Nummern bereits?
        if b_number != w.box_number:
            try:
                existing_box_number = db.session.query(warehouse_table.box_number).filter(
                    warehouse_table.box_number == b_number).first()
            except SQLAlchemyError as e:
                flash(f'Änderungen konnten nicht gespeichert werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("warehouse_bp.warehouse_management"))

            if existing_box_number is not None:

                flash("Die angegebene Kisten-ID wird bereits verwendet.", 'danger')
                return redirect(url_for("warehouse_bp.warehouse_edit", w_id=w_id))

        try:
            stmt = (
                update(warehouse_table).where(warehouse_table.warehouse_id == w_id).values(
                    shelf_number=s_number,
                    compart_number=c_number,
                    box_number=b_number,
                    description=request.form.get("warehouse_description"))
            )

            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect("warehouse_bp.warehouse_management")

        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    #get initial selection of compart numbers based on shelf number of warehouse entry
    try:
        compart_numbers = [r.compart_number for r in
                           db.session.query(warehouse_table.compart_number).filter(
                               warehouse_table.shelf_number == w.shelf_number).distinct()]
    except SQLAlchemyError as e:
        flash(f' Lager-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    try:
        shelf_numbers = get_shelf_numbers()
    except Exception as e:
        flash(f' Lager-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("warehouse_bp.warehouse_management"))

    return render_template("warehouse_edit.html", sel_warehouse=w, shelf_numbers=shelf_numbers,
                           initial_compart_numbers=compart_numbers)
