from flask import render_template, redirect, Blueprint, request, jsonify, flash, url_for
from flask_login import login_required
from application import db, app
from application.models import category_table, item_table
from sqlalchemy import update
from application.forms import current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from application.category.category_func import get_values_from_category_form, get_existing_categories, create_cat_dict


category_bp = Blueprint('category_bp', __name__, template_folder='templates')


#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

#create selection options for accessory_for
@category_bp.route('/ajax_get_accessory_entries', methods=['GET'])
def ajax_get_accessory_entries():
    try:
        accessories = [r.accessory_for for r in
                       db.session.query(category_table.accessory_for).filter(category_table.accessory_for != '',
                                                                              category_table.accessory_for != 'None').distinct()]
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify('error')
    return jsonify(accessories)


#create selection options for spare_part_for
@category_bp.route('/ajax_get_spare_part_entries', methods=['GET'])
def ajax_get_spare_part_entries():
    try:
        spare_parts = [r.spare_part_for for r in
                       db.session.query(category_table.spare_part_for).filter(category_table.spare_part_for != '',
                                                                              category_table.spare_part_for != 'None').distinct()]
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify('error')
    return jsonify(spare_parts)


#MAIN+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# toDo Kategorie Bezeichnungen sollten eindeutig sein!
@category_bp.route('/categories', methods=['POST', 'GET'])
@login_required
def categories():

    if current_user.admin_role != 1:
        return render_template("restricted.html")

    if request.method == "POST":

        if 'new_legal_descr' in request.form:

            kat_id=request.form.get('kat_id')
            try:
                stmt = (
                    update(category_table).where(category_table.category_id == kat_id).values(
                        legal_descr=request.form.get('new_legal_descr') )
                )

                db.engine.execute(stmt)
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(
                    f' Änderungen am Rechtstext konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.error(
                    f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))

            flash(f"Rechtstext für Kategorie {kat_id} aktualisiert.", 'success')
            return redirect(url_for("category_bp.categories"))

        elif 'delete_button' in request.form:

            try:
                category_used = db.session.query(item_table.item_id).filter(item_table.id_category == request.form.get('delete_button'), item_table.id_sale == None).first()
            except SQLAlchemyError as e:
                flash(f' Kategorie konnte nicht gelöscht werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))

            if category_used is not None:
                flash("Die Kategorie konnte nicht gelöscht werden, da sie verwendet wird.", 'danger')
                return redirect(url_for("category_bp.categories"))

            try:
                db.session.query(category_table).filter(category_table.category_id == request.form.get('delete_button')).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Kategorie konnte nicht gelöscht werden (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))

            flash("Kategorie wurde gelöscht.", 'success')
            return redirect(url_for("category_bp.categories"))

        else:
            superior_category, accessory_for, spare_part_for = get_values_from_category_form()

            try:
                k = category_table(name=request.form.get('kategorie_bezeichnung'), superior_category=superior_category,
                                   accessory_for=accessory_for,
                                   spare_part_for=spare_part_for)

                db.session.add(k)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Kategorie konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))

            flash("Kategorie wurde erfolgreich hinzugefügt.", 'success')
            return redirect(url_for("category_bp.categories"))

    if "lvl1" not in request.args:
        lvl1="alle"
        lvl2=None
        lvl3=None
    else:
        lvl1 = request.args.get("lvl1")
        lvl2 = request.args.get("lvl2")
        lvl3 = request.args.get("lvl3")

    try:
        all_categories, all_categories_labels = get_existing_categories(lvl1, lvl2, lvl3)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    try:
        cat_dict = create_cat_dict()  #used for selection in "add category"
    except Exception as e:
        flash(str(e), 'danger')
        return redirect("home_bp.dashboard")

    return render_template("categories.html", t_header_1=all_categories_labels, t_content_1=all_categories, kat_dict=cat_dict)


@category_bp.route('/category_edit/<int:idd>', methods=['GET', 'POST'])
@login_required
def category_edit(idd):

    try:
        category_exists = db.session.query(category_table.category_id).filter(category_table.category_id == idd).first()
    except SQLAlchemyError as e:
        flash(f'Kategorie-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("category_bp.categories"))

    if category_exists is None:
        flash("Die Kategorie existiert nicht.", 'danger')
        return redirect(url_for("category_bp.categories"))

    if request.method == "POST":

        superior_category, accessory_for, spare_part_for = get_values_from_category_form()

        try:
            stmt = (
                update(category_table).where(category_table.category_id == idd).values(
                    name=request.form.get('kategorie_bezeichnung'),
                    superior_category=superior_category,
                    accessory_for=accessory_for,
                    spare_part_for=spare_part_for)
            )

            db.engine.execute(stmt)
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Änderungen an Kategorie konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("category_bp.categories"))

        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(url_for("category_bp.categories"))

    try:
        cat_dict = create_cat_dict()
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    try:
        cat = db.session.query(category_table).filter(category_table.category_id == idd).first()
    except SQLAlchemyError as e:
        flash(f'Kategorie-Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("category_bp.categories"))

    #dictionary for existing category entry, to display editable values
    cat = {
        "ueber_kategorie": cat.superior_category,
        "kategorie_bezeichnung": cat.name,
        "zubehoer_von": cat.accessory_for,
        "ersatzteil_von": cat.spare_part_for
    }


    #create selection options (in this case to complicated to do via ajax bcs of pre-selected value)
    try:
        existing_accessory_for_entries = [r.accessory_for for r in
                       db.session.query(category_table.accessory_for).filter(category_table.accessory_for != '',
                                                                              category_table.accessory_for != 'None').distinct()]
    except SQLAlchemyError as e:
        flash(f' Existierender Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("catgeory_bp.categories"))

    try:
        existing_spare_part_entries = [r.spare_part_for for r in
        db.session.query(category_table.spare_part_for).filter(category_table.spare_part_for != '',
                                                            category_table.spare_part_for != 'None').distinct()]
    except SQLAlchemyError as e:
        flash(f' Existierender Eintrag konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("catgeory_bp.categories"))


    return render_template("category_edit.html", kat_id=idd, kat_dict=cat_dict, sel_kat=cat,
                           accessories=existing_accessory_for_entries,
                           spare_parts=existing_spare_part_entries)


