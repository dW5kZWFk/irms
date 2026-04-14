from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from flask_paginate import Pagination, get_page_parameter
from application import db, app
from application.models import purchase_table
from application.purchase_sale.purchase_sale_func import get_all_purchases, get_all_sales, get_all_sales_by_date, \
    get_all_sales_by_id, get_all_purchases_by_date, get_all_purchases_by_identifier
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


purchase_sale_bp = Blueprint('purchase_sale_bp', __name__,
    template_folder = 'templates', url_prefix='')


@purchase_sale_bp.route("/sales", methods=['GET', 'POST'])
@login_required
def sales():

    per_page = 6
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    if "date" in request.args:
        date = request.args.get("date")
        if date == '':
            return redirect(url_for("purchase_sale_bp.sales"))

        try:
            sales_dict, sales_total = get_all_sales_by_date(date, per_page, offset)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("purchase_sale_bp.sales"))

        if len(sales_dict) == 0:
            flash("An diesem Tag wurden keine Verkäufe eingetragen.", 'info')
            return redirect(url_for("purchase_sale_bp.sales"))

        msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(sales_dict)} </b>  von <b class=\"bg-white\"> {sales_total} </b>."
        pagination = Pagination(page=page, total=sales_total, per_page=per_page, offset=offset, record_name='Verkäufe',
                                display_msg=msg, css_framework='bootstrap5')

        return render_template("sales.html", sales_dict=sales_dict, pagination=pagination, last_date=date)

    if "id" in request.args:

        id = request.args.get("id")

        if id == '':
            return redirect(url_for("purchase_sale_bp.sales"))

        try:
            sales_dict = get_all_sales_by_id(id)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("purchase_sale_bp.sales"))

        if len(sales_dict) == 0:
            flash("Es wurde kein Verkaufs-Eintrag mit dieser ID gefunden.", 'info')
            return redirect(url_for("purchase_sale_bp.sales"))

        return render_template("sales.html", sales_dict=sales_dict, last_id=id)


    try:
        sales_dict, sales_total = get_all_sales(per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(sales_dict)} </b>  von <b class=\"bg-white\"> {sales_total} </b>."
    pagination = Pagination(page=page, total=sales_total, per_page=per_page, offset=offset, record_name='Verkäufe', display_msg=msg, css_framework='bootstrap5')

    return render_template("sales.html", sales_dict=sales_dict, pagination=pagination)


@purchase_sale_bp.route("/purchase", methods=['GET', 'POST'])
@login_required
def purchase():

    if request.method == "POST":

        if "delete_purchase" in request.form:

            p_id = request.form.get("delete_purchase")

            try:
                db.session.query(purchase_table).filter(
                    purchase_table.purchase_id == p_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Einkauf konnte nicht gelöscht werden (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path} (delete_purchase). Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("purchase_sale_bp.purchase"))

            flash("Einkauf wurde gelöscht.", 'success')
            return redirect(url_for("purchase_sale_bp.purchase"))

        try:
            p = purchase_table(price=request.form.get('price').replace(',', '.'), supplier=request.form.get('supplier'), identifier=request.form.get('identifier'), id_created_by=current_user.user_id)
            db.session.add(p)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Einkauf konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("purchase_sale_bp.purchase"))

        flash('Einkauf wurde hinzugefügt.', 'success')
        return redirect(url_for("purchase_sale_bp.purchase"))

    per_page = 7
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    if "date" in request.args:
        date = request.args.get("date")
        if date == '':
            return redirect(url_for("purchase_sale_bp.purchase"))

        try:
            purchase_dict, purchases_total = get_all_purchases_by_date(date, per_page, offset)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("purchase_sale_bp.purchase"))

        if len(purchase_dict) == 0:
            flash("An diesem Tag wurden keine Einkäufe eingetragen.", 'info')
            return redirect(url_for("purchase_sale_bp.purchase"))
        msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(purchase_dict)} </b>  von <b class=\"bg-white\"> {purchases_total} </b>."
        pagination = Pagination(page=page, total=purchases_total, per_page=per_page, offset=offset, record_name='Einkäufe',
                                display_msg=msg, css_framework='bootstrap5')
        return render_template("purchase.html", purchase_dict=purchase_dict, pagination=pagination, last_date=date)

    if "id" in request.args:
        identifier = request.args.get("id")
        if identifier == '':
            return redirect(url_for("purchase_sale_bp.purchase"))

        try:
            purchase_dict, purchases_total = get_all_purchases_by_identifier(identifier, per_page, offset)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("purchase_sale_bp.purchase"))

        if len(purchase_dict) == 0:
            flash("Es wurde kein Einkauf mit diesem Identifikator gefunden.", 'info')
            return redirect(url_for("purchase_sale_bp.purchase"))
        msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(purchase_dict)} </b>  von <b class=\"bg-white\"> {purchases_total} </b>."
        pagination = Pagination(page=page, total=purchases_total, per_page=per_page, offset=offset, record_name='Einkäufe',
                                display_msg=msg, css_framework='bootstrap5')
        return render_template("purchase.html", purchase_dict=purchase_dict, pagination=pagination, last_id=identifier)

    try:
        purchase_dict, purchases_total = get_all_purchases(per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(purchase_dict)} </b>  von <b class=\"bg-white\"> {purchases_total} </b>."
    pagination = Pagination(page=page, total=purchases_total, per_page=per_page, offset=offset, record_name='Einkäufe',
                            display_msg=msg, css_framework='bootstrap5')

    return render_template("purchase.html", purchase_dict=purchase_dict, pagination=pagination)