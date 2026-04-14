import json
import os
#import flask_user
from flask import render_template, request, redirect, jsonify, url_for, session, flash
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_parameter
from application import db, app
from application.models import repair_table, repair_order_table, spare_part_table, item_table, category_table, customer_table, service_table, sale_table, User
from flask import Blueprint
from application.category.category_func import get_legal_descr
from application.customer.customer_func import get_all_customers, get_single_customer_name, add_customer
from application.service.service_func import get_all_services, get_single_service
from application.inventory.inventory_func import get_single_item, get_single_item_description_order, \
    check_item_deleted_or_sold, check_item_deleted_or_sold_or_in_repair
from application.repair.repair_func import check_repair_state, send_mail_to_customer, get_repair_orders_dict_list,\
    add_repair, update_repair_edit, delete_spare_part, get_internal_repair_dict, check_spare_part_not_available, check_repair_order_not_available
from sqlalchemy import update, and_
from datetime import datetime
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from babel.dates import format_datetime

repair_bp = Blueprint('repair_bp', __name__, template_folder='templates', url_prefix='')

@repair_bp.route('/base_o_id_input', methods=['GET'])
def base_o_id_input():
    o_id = request.args.get('repair_order_id_input')
    o_id = o_id.replace(" ","")
    try:
        repair_order_results = db.session.query(repair_order_table.repair_order_id, repair_order_table.state).filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        flash(f' Auftrags-Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(request.referrer)

    if repair_order_results is not None:
        if repair_order_results.state=="abgeschlossen":
            return redirect(url_for('repair_bp.repair_orders_finished', id=o_id))
        else:
            return redirect(url_for('repair_bp.repair_orders_i', o_id=o_id))
    else:
        flash(f'Auftrag (ID: {o_id}) existiert nicht.', 'danger')
        return redirect(request.referrer)

#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@repair_bp.route('/ajax_get_finish_order_details', methods=['GET'])
def ajax_get_finish_order_details():
    s_id = request.args.get('service_id')
    o_id = request.args.get('order_id')

    #toDo: testen ob die abfrage notwendig ist
    if s_id == '-':
        s_price = '-'
        s_name = '-'
    else:
        try:
            service_result = db.session.query(service_table).filter(service_table.service_id == s_id).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        if service_result is None:
            s_price = '-'
            s_name = '-'
        else:
            s_name = service_result.name
            s_price = service_result.price
            if s_price:
                s_price = str(s_price).replace('.', ',')

    try:
        repair_result = db.session.query(repair_table.price).join(repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    if repair_result is None:
        r_price = '-'
    else:
        r_price = repair_result.price
        if r_price:
            r_price = str(r_price).replace('.', ',')
        else:
            r_price = '+'

    sum_price = Decimal(0.00)
    if r_price != '+' and r_price != '-':
        sum_price = sum_price + repair_result.price

    if s_price != '-':
        sum_price = sum_price + service_result.price

    try:
        customer_result = db.session.query(customer_table.name).join(repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")



    file_path = os.path.join(app.root_path, 'static/mail_content.txt')

    try:
        with open(file_path, 'r') as f:
            email_content = f.read()
    except OSError as e:
        app.logger.warning(f"Failed to read E-Mail from OS.  Time: {datetime.now()}. Exception: {e}")
        return jsonify("error")

    email_content_new = email_content.replace('{kundenname}', customer_result.name)

    o_details = {
        "s_name": s_name,
        "s_price": s_price,
        "r_price": r_price,
        "email": email_content_new,
        "sum_price": str(sum_price).replace('.', ',')
    }

    return jsonify(o_details)


@repair_bp.route('/ajax_spare_parts_search', methods=['GET'])
def ajax_spare_parts_search():
    et = request.args.get('et')
    search_value_cat = request.args.get('search_value_cat')
    search_value_name = request.args.get('search_value_name')

    if et == 'alle':
        try:
            items = db.session.query(item_table.item_id, item_table.state, item_table.name.label('i_name'), category_table.superior_category, category_table.name.label('c_name'))\
                             .join(category_table)\
                             .filter(and_
                                        (and_(category_table.superior_category.ilike('%'+search_value_cat+'%'), category_table.name.ilike('%'+search_value_name+'%'))),
                                        item_table.internal == 1, item_table.id_sale == None, category_table.spare_part_for != '').all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

    else:
        try:
            items = db.session.query(item_table.item_id, item_table.state, item_table.name.label('i_name'), category_table.superior_category,
                                     category_table.name.label('c_name')) \
                                    .join(category_table) \
                                    .filter(and_
                                            (and_(category_table.superior_category.ilike('%'+search_value_cat+'%'),
                                                    category_table.name.ilike('%'+search_value_name+'%'))),
                                                    item_table.internal == 1, item_table.id_sale == None, category_table.spare_part_for == et).all()
            #has to be internal ( not in an active order) and has to be category "spare_part" and has to be not sold
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

    items_list = []
    if len(items) == 0 or items is None:
        return jsonify("empty")
    else:
        for i in items:

            try:
                #not displayed if it is already used as spare_part:
                is_spare_part = db.session.query(spare_part_table.spare_part_id).join(item_table).filter(item_table.item_id == i.item_id).first()

            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return jsonify("error")

            if is_spare_part is None:
                i_dict = {
                    "id": i.item_id,
                    "state": i.state,
                    "category": i.superior_category,
                    "c_name": i.c_name,
                    "i_name": i.i_name
                }
                items_list.append(i_dict)
        return jsonify(items_list)



@repair_bp.route('/ajax_customer_search', methods=['GET'])
def ajax_customer_search():
    search_value = request.args.get('search_value')

    if search_value is not None:
        try:
            customers = db.session.query(customer_table).filter(customer_table.name.ilike('%'+search_value+'%')).all()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify("error")

        if len(customers) == 0:
            return jsonify("empty")
        else:
            customer_list = []
            for c in customers:
                c_dict = {
                    "id": c.customer_id,
                    "name": c.name,
                    "email": c.email,
                    "phone_number": c.phone_number,
                    "address": c.address
                }
                customer_list.append(c_dict)
            return jsonify(customer_list)


@repair_bp.route('/ajax_sp_state_change', methods=['GET'])
def ajax_sp_state_change():

    sp_id = request.args.get('sp_id')

    try:
        not_available = check_spare_part_not_available(sp_id)
    except Exception as e:
        return jsonify("error")

    if not_available:
        return jsonify("error_not_available")

    new_state = request.args.get('new_state')

    stmt = update(spare_part_table).where(spare_part_table.spare_part_id == sp_id).values(
        state=new_state)
    try:
        db.session.execute(stmt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error1")

    try:
        r_id = db.session.query(spare_part_table.id_repair).filter(spare_part_table.spare_part_id == sp_id).first().id_repair
        update_repair_edit(r_id, current_user.user_id)
    except Exception as e:
        return jsonify("error2")
    return jsonify('success')


@repair_bp.route('/ajax_order_state_change', methods=['GET'])
def ajax_order_state_change():
    new_state = request.args.get('new_state')

    o_id = request.args.get('o_id')

    try:
        not_available = check_repair_order_not_available(o_id)
    except Exception as e:
        return jsonify("error1")

    if not_available:
        return("error_not_available")

    stmt = update(repair_order_table).where(repair_order_table.repair_order_id == o_id).values(
        state=new_state, edit_date=datetime.now(), id_edited_by=int(current_user.user_id))
    try:
        db.session.execute(stmt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    return jsonify('success')


#status kann nur geändert werden, wenn keine Ersatzteile eingetragen sind, oder alle Ersatzteile "vorhanden" sind
#d.h. wenn der Reparatur status "laufend" / "neu" / "abgeschlossen" ist
@repair_bp.route('/ajax_repair_state_change', methods=['GET'])
def ajax_repair_state_change():

    r_id = request.args.get('r_id')
    #check state change availability (item not sold/ deleted), current repair state in changable mode
    try:
        check_repair_state(r_id)
        i_id = db.session.query(item_table.item_id).filter(item_table.id_repair == r_id).first()
        item_not_available = check_item_deleted_or_sold(i_id.item_id)

        repair_results = db.session.query(repair_table.state).filter(repair_table.repair_id == r_id).first()
    except Exception as e:
        app.logger.warning("Exception in ajax_repair_state_change - check availability. {request.path}. Time: {datetime.now()}. Exception: {e}\n ")
        return jsonify("error")

    if item_not_available or repair_results.state != "neu" and repair_results.state != "laufend" and repair_results.state != "abgeschlossen":
        return jsonify("error_not_available")

    stmt = update(repair_table).where(repair_table.repair_id == request.args.get('r_id')).values(state=request.args.get('new_state'), edit_date=datetime.now(), id_edited_by=current_user.user_id)
    try:
        db.session.execute(stmt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")
    return jsonify('success')


@repair_bp.route('/ajax_print_order_data', methods=['GET'])
def ajax_print_order_data():
    r_o_id = request.args.get('id')
    stmt = f'''SELECT customer.name, customer.address, customer.email, customer.phone_number,
              repair_order.id_item, repair_order.description as 'o_description', service.name as 'service_name',
              service.price as 'service_price'
              FROM repair_order  
              INNER JOIN customer ON repair_order.id_customer = customer.customer_id
              LEFT JOIN repair ON repair_order.repair_order_id = repair.id_repair_order
              LEFT JOIN service ON repair_order.id_service = service.service_id
              WHERE repair_order.repair_order_id = {r_o_id};  '''
    try:
        results = db.session.execute(stmt).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    try:
        device = get_single_item_description_order(results.id_item)
    except Exception as e:
        return jsonify("error")

    try:
        legal_descr = get_legal_descr(results.id_item)
    except Exception as e:
        return jsonify("error")

    #get info about gtc from json file
    file = os.path.join(app.root_path, 'static/contact_info.json')
    try:
        with open(file, 'r') as json_file:
            data = json.loads(json_file.read())
    except Exception as e:
        return jsonify("error")

    if results.email is None:
        email = ''
    else:
        email = results.email

    if results.phone_number is None:
        phone_number = ''
    else:
        phone_number = results.phone_number

    if results.o_description is None:
        o_description = ''
    else:
        o_description = results.o_description

    if results.address is None:
        address = ''
    else:
        address = results.address


    data = {
        "id": r_o_id,
        "name": results.name,
        "email": email,
        "address": address,
        "number": phone_number,
        "device": device,
        "legal_descr": legal_descr, #Rechtstext Kategorie
        "gtc_address": data["address"],
        "gtc_mail": data["mail"],
        "gtc_phone": data["phone"],
        "gtc_legal": data["legal_general"], #Haftungsausschluss
        "order_description": o_description,
        "service_name": results.service_name,
        "service_price": results.service_price
        #"repair_description": r_description,
    }

    return jsonify(data)


#print repair_details:
@repair_bp.route('/ajax_print_repair_data', methods=['GET'])
def ajax_print_repair_data():
    #item_table.name, item_table.serial_number, item_table.description (Zust. bei Abgabe)
    #repair_table.description (Diagnose u. Reparatur)
    #repair_order_table.description (Fehlerbeschreibung)

    r_o_id = request.args.get('o_id')
    stmt = f'''select item.name, item.serial_number, item.description as 'i_description', repair_order.description as 'o_description',
                      repair.description as 'r_description', repair.price as 'r_price', service.price as 's_price'   
               FROM repair_order 
               INNER JOIN repair ON repair_order.repair_order_id = repair.id_repair_order 
               INNER JOIN item ON repair_order.id_item=item.item_id
               LEFT JOIN service ON repair_order.id_service = service.service_id
               WHERE repair_order_id={r_o_id};'''

    try:
        results = db.session.execute(stmt).first()

    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")
    print(results)
    print(results.r_price)
    print(results.s_price)
    data = {
        "name": results.name,
        "serial_number": results.serial_number,
        "i_descr": results.i_description,
        "o_descr": results.o_description,
        "r_descr": results.r_description,
        'r_price':results.r_price,
        's_price':results.s_price
        #"repair_description": r_description,
    }

    return jsonify(data)
#MAIN/ORDERS++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#select customer
@repair_bp.route('/repair_input', methods=['POST', 'GET'])
@login_required
def repair_input():

    if not session.get('last_repair_input_page'):
        session['last_repair_input_page'] = 'repair_input.html'

    if session['last_repair_input_page'] != 'repair_input.html':
        return redirect(session['last_repair_input_page'])

    session['order_created'] = False

    if request.method == "POST":
        #customer is added:
        if request.form.get("add_customer") is not None:
            try:
                c_id = add_customer()
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for('repair_bp.repair_input'))

            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c",
                                                        c_id=c_id)
            return redirect(url_for("repair_bp.repair_input_c", c_id=c_id))

        #customer is selected:
        if request.form.get("customer_id") is not None:
            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c", c_id=request.form.get("customer_id"))
            return redirect(url_for("repair_bp.repair_input_c", c_id=request.form.get("customer_id")))

    try:
        all_customers, customers_total = get_all_customers(0,0)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    return render_template("repair_input.html", all_customers=all_customers)


@repair_bp.route('/repair_input_c/<int:c_id>', methods=['POST', 'GET'])
@login_required
def repair_input_c(c_id):

    if session['last_repair_input_page'] != url_for('repair_bp.repair_input_c', c_id=c_id):
        return redirect(session['last_repair_input_page'])

    #if customer doesn't exist anymore -> return to start page
    try:
        customer_exists = db.session.query(customer_table.customer_id).filter(customer_table.customer_id == c_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash(f"Seite konnte nicht geladen werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
        return redirect(url_for('home_bp.dashboard'))

    if customer_exists is None:
        flash("Der Kunde existiert nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))

    if request.method == "POST":

        #customer is added:
        if request.form.get("add_customer") is not None:
            try:
                c_id = add_customer()
            except Exception as e:
                flash(str(e), 'danger')
            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c", c_id=c_id)
            return redirect(url_for("repair_bp.repair_input_c", c_id=c_id))

        if "abort" in request.form:
            session['last_repair_input_page'] = 'repair_input.html'
            return redirect(url_for('repair_bp.repair_input'))

        #customer is changed:
        if request.form.get("customer_id") is not None:
            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c", c_id=request.form.get("customer_id"))
            return redirect(url_for("repair_bp.repair_input_c", c_id=request.form.get("customer_id")))

    try:
        all_customers, customers_total = get_all_customers(0,0)
        customer = get_single_customer_name(c_id)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    return render_template("repair_input_c.html", all_customers=all_customers, customer=customer)


@repair_bp.route('/repair_input_c_i/<int:c_id>/<int:i_id>/', methods=['POST', 'GET'])
@login_required
def repair_input_c_i(c_id, i_id):

    if session['last_repair_input_page'] != url_for('repair_bp.repair_input_c_i', c_id=c_id, i_id=i_id):
        return redirect(session['last_repair_input_page'])

    #if customer or item doesn't exist anymore -> return to start page
    try:
        item_exists = db.session.query(item_table.item_id).filter(item_table.item_id == i_id).first()
        customer_exists = db.session.query(customer_table.customer_id).filter(
            customer_table.customer_id == c_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(
            f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash(f"Seite konnte nicht geladen werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}",
              'danger')
        return redirect(url_for('home_bp.dashboard'))

    if customer_exists is None:
        if item_exists is not None:
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Kunden-Eintrag existiert nicht und das Item konnte nicht gelöscht werden. Manuelle Löschung notwendig! (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))
            flash("Der Kunde existiert nicht. Das Item wurde gelöscht.", 'danger')
        else:
            flash("Der Kunde und das Item existieren nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))

    if item_exists is None:
        flash("Das Item existiert nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))


    if request.method == "POST":
        if request.form.get("service_id") is not None:
            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c_i_s", c_id=c_id, i_id=i_id, s_id=request.form.get("service_id"))
            return redirect(url_for("repair_bp.repair_input_c_i_s", c_id=c_id, i_id=i_id, s_id=request.form.get("service_id")))

        if "abort" in request.form:
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' FATAL ERROR Item (ID: {i_id}) konnte nicht gelöscht werden. Manuelle Löschung erforderlich. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. MANUALLY DELETE ITEM-ID:{i_id}!! Time: {datetime.now()}. Exception: {e}\n')
            session['last_repair_input_page'] = 'repair_input.html'
            return redirect(url_for('repair_bp.repair_input'))

        if "ok" in request.form:
            session['last_repair_input_page'] = 'repair_input.html'
            return redirect(url_for('repair_bp.repair_orders_i', o_id=session.get('order_created')))

    if request.method == "POST" and "create_order" in request.form:
        o = repair_order_table(id_item=i_id, description=request.form.get("description"), state="angenommen", id_customer=c_id, id_edited_by=current_user.user_id)
        try:
            db.session.add(o)
            db.session.flush()
            o_id = o.repair_order_id
            #repair entries not created per default anymore
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Auftrag konnte nicht erstellt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(session['last_repair_input_page'])

        session['order_created'] = o_id
        return redirect(url_for("repair_bp.repair_input_c_i", c_id=c_id, i_id=i_id))

    try:
        all_services, services_total = get_all_services(0, 0)
        item = get_single_item(i_id)
        customer = get_single_customer_name(c_id)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("home_bp.dashboard"))

    return render_template("repair_input_c_i.html", item=item, customer=customer, all_services=all_services)


@repair_bp.route('/repair_input_c_i_s/<int:c_id>/<int:i_id>/<int:s_id>', methods=['POST', 'GET'])
@login_required
def repair_input_c_i_s(c_id, i_id, s_id):

    if session['last_repair_input_page'] != url_for('repair_bp.repair_input_c_i_s', c_id=c_id, i_id=i_id, s_id=s_id):
        return redirect(session['last_repair_input_page'])

        #if customer or item doesn't exist anymore -> return to start page
    try:
        item_exists = db.session.query(item_table.item_id).filter(item_table.item_id == i_id).first()
        customer_exists = db.session.query(customer_table.customer_id).filter(
            customer_table.customer_id == c_id).first()
        service_exists = db.session.query(service_table.service_id).filter(service_table.service_id == s_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(
            f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash(f"Seite konnte nicht geladen werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}",
              'danger')
        return redirect(url_for('home_bp.dashboard'))

    if customer_exists is None:
        if item_exists is not None:
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Kunden-Eintrag existiert nicht und das Item konnte nicht gelöscht werden. Manuelle Löschung notwendig! (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))
            flash("Der Kunde existiert nicht. Das Item wurde gelöscht.", 'danger')
        else:
            flash("Der Kunde und das Item existieren nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))

    if service_exists is None:
        if item_exists is not None:
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Service existiert nicht und das Item konnte nicht gelöscht werden. Manuelle Löschung notwendig! (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("category_bp.categories"))
            flash("Der Service existiert nicht. Das Item wurde gelöscht.", 'danger')
        else:
            flash("Der Service und das Item existieren nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))

    if item_exists is None:
        flash("Das Item existiert nicht.", 'danger')
        session['last_repair_input_page'] = 'repair_input.html'
        return redirect(url_for('repair_bp.repair_input'))


    if request.method == "POST":

        if "abort" in request.form:
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' FATAL ERROR Item (ID: {i_id}) konnte nicht gelöscht werden. Manuelle Löschung erforderlich. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. MANUALLY DELETE ITEM-ID:{i_id}!! Time: {datetime.now()}. Exception: {e}\n')
            session['last_repair_input_page'] = 'repair_input.html'
            return redirect(url_for('repair_bp.repair_input'))

        if "ok" in request.form:
            session['last_repair_input_page'] = 'repair_input.html'
            return redirect(url_for('repair_bp.repair_orders_i', o_id=session.get('order_created')))

        if request.method == "POST" and "create_order" in request.form:
            o = repair_order_table(id_item=i_id, id_service=s_id, state="angenommen", description=request.form.get("description"),  id_customer=c_id, id_edited_by=current_user.user_id)
            try:
                db.session.add(o)
                db.session.flush()
                o_id = o.repair_order_id

                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Auftrag konnte nicht erstellt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(session['last_repair_input_page'])

            session['order_created'] = o_id
            #todo: prevent resend on refresh!
            return redirect(url_for("repair_bp.repair_input_c_i_s", c_id=c_id, i_id=i_id, s_id=s_id))

    try:
        service = get_single_service(s_id)
        item = get_single_item(i_id)
        customer = get_single_customer_name(c_id)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("home_bp.dashboard"))

    return render_template("repair_input_c_i_s.html", item=item, customer=customer, service=service)


@repair_bp.route('/repair_orders', methods=['POST', 'GET'])
@login_required
def repair_orders():

    if request.referrer is None:
        flash("request.referrer is None", 'info')
        return redirect(url_for('home_bp.dashboard'))

    if not "repair_orders" in request.referrer or "repair_orders_finished" in request.referrer and not "repair_input_c_i" in request.referrer:
        if 'page' not in request.args:
            #wenn das page cookie noch nicht gesetzt ist, wird es Seite 1
            if session.get('last_repair_order_page'):
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))
    elif 'name' not in request.args:
        if 'page' not in request.args:
           session['last_repair_order_page'] = 1
        else:
            session['last_repair_order_page'] = request.args.get('page')

    if request.method == "POST":

        if "new_repair_price" in request.form:
            price = request.form.get('new_repair_price')
            r_id = request.form.get('r_id')
            if price == '':
                price = None
            else:
                price = price.replace(',', '.')
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(price=price,
                                                                                     edit_date=datetime.now(),
                                                                                     id_edited_by=current_user.user_id)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Änderungen konnten nicht gespeichert werden (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))
            flash("Änderungen wurden gepspeichert.", 'success')
            return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

        #session['last_repair_order_page'] = request.args.get('page')

        if "new_order_description" in request.form:
            o_id = request.form.get("order_id")

            try:
                not_available = check_repair_order_not_available(o_id)
            except Exception as e:
                flash(f' Auftragsbeschreibung konnte nicht angepasst werden. (SQLAlchemy QUERY error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))
            if not_available:
                flash("Auftrag wurde bereits abgeschlossen oder gelöscht.", 'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

            stmt = (
                update(repair_order_table).where(repair_order_table.repair_order_id == o_id)).values(
                id_edited_by=current_user.user_id, edit_date=datetime.now(), description=request.form.get("new_order_description")
            )
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Auftragsbeschreibung konnte nicht angepasst werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))

            flash("Auftragsbeschreibung wurde angepasst.", 'success')
            if "name" in request.referrer:
                return redirect(request.referrer)
            return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

        if "add_order_description" in request.form:
            o_id = request.form.get("order_id")

            try:
                not_available = check_repair_order_not_available(o_id)
            except Exception as e:
                flash(f' Auftragsbeschreibung konnte nicht hinzugefügt werden. (SQLAlchemy QUERY error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))
            if not_available:
                flash("Auftrag wurde bereits abgeschlossen oder gelöscht.", 'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

            stmt = (
                update(repair_order_table).where(repair_order_table.repair_order_id == o_id)).values(
                id_edited_by=current_user.user_id, edit_date=datetime.now(), description=request.form.get("add_order_description")
            )
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Auftragsbeschreibung konnte nicht hinzugefügt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))

            flash("Auftragsbeschreibung wurde hinzugefügt.", 'success')
            if "name" in request.referrer:
                return redirect(request.referrer)
            return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))


        if "add_repair_entry" in request.form:

            try:
                not_available = check_item_deleted_or_sold_or_in_repair(request.form.get("item_id"))
            except Exception as e:
                flash(f' Auftragsbeschreibung konnte nicht angepasst werden. (SQLAlchemy QUERY error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))
            if not_available:
                flash("Auftrag wurde bereits abgeschlossen oder gelöscht, oder das Item besitzt bereits einen Reparatur-Eintrag.", 'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))

            try:
                r_id = add_repair(request.form.get("item_id"))
            except Exception as e:
                flash(str(e), 'danger')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders"))
            stmt = (
            update(repair_table).where(repair_table.repair_id == r_id)).values(
                id_repair_order=request.form.get("order_id"), id_edited_by=current_user.user_id)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Reparatur-Eintrag konnte nicht hinzugefügt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(request.referrer)
                return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            flash("Reparatur-Eintrag  wurde hinzugefügt.", 'success')
            if "name" in request.referrer:
                return redirect(request.referrer)
            return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

        #repair_order und item löschen
        if "delete_order" in request.form:

            i_id = request.form.get("delete_item")
            o_id = request.form.get("delete_order")
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.query(repair_order_table).filter(repair_order_table.repair_order_id == o_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy DELETE exception on logout. Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Item und Auftrag konnten nicht gelöscht werden.(SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                return redirect(url_for("repair_bp.repair_orders"))

            flash(f"Das Item {i_id} und der Auftrag {o_id} wurden erfolgreich gelöscht.", 'success')
            if "name" in request.referrer:
                return redirect(url_for("repair_bp.repair_orders"))
            return redirect(url_for("repair_bp.repair_orders", page=1))

        if "finish_order" in request.form:
            o_id = request.form.get("order_id")

            try:
                not_available = check_repair_order_not_available(o_id)
            except Exception as e:
                flash(f' Auftragsbeschreibung konnte nicht angepasst werden. (SQLAlchemy QUERY error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders"))
            if not_available:
                flash("Auftrag wurde bereits abgeschlossen oder gelöscht.", 'danger')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders"))

            #finish order:
            add_price = request.form.get("add_price")
            if add_price is None or add_price == '':
                add_price = 0
            else:
                add_price = add_price.replace(',','.')

            s_id = request.form.get("service_id")
            c_id = request.form.get("customer_id")
            r_id = request.form.get("repair_id")

            now = datetime.now()

            try:
                i_id = db.session.query(repair_order_table.id_item).filter(repair_order_table.repair_order_id == o_id).first().id_item
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item ID). Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders_finished", page=session.get('last_repair_order_page')))

            #Auftrag-------------------------------------
            try:
                results_repair_order = db.session.query(repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query repair_order). Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            description = "Abgeschlossener Auftrag - ID:" +str(o_id) + '\n\n Start-Datum: '+str(results_repair_order.issue_date) + '\n Liefer-Datum: '+ str(now) +'\n'
            description += "Beschreibung: "+str(results_repair_order.description) +'\n\n'

            #Kunde-----------------------------------------------------------------------------------------------
            try:
                customer_results = db.session.query(customer_table).filter(customer_table.customer_id == c_id).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query customer). Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            description += "Kunde: " + str(customer_results.name)+'\n\n'

            #Item----------------------------------------
            try:
                item_results = db.session.query(item_table.name, item_table.serial_number, item_table.description, item_table.id_category).filter(item_table.item_id==i_id).first()
                category_results = db.session.query(category_table.superior_category, category_table.name, category_table.spare_part_for, category_table.accessory_for).filter(
                    category_table.category_id == item_results.id_category).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item/Category). Time: {datetime.now()}. Exception: {e}\n')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            description += "Item -ID: "+str(i_id)+' , Kategorie:' + str(category_results.spare_part_for) + str(category_results.accessory_for) + ' ' + str(category_results.superior_category) + ' ' + str(category_results.name) +'\n'
            description += "Bezeichnung: " + str(item_results.name) +'\n'
            description += "Seriennummer: " + str(item_results.serial_number) + '\n'
            description += "Beschreibung: " + str(item_results.description) +'\n\n'

            #service-------------------------------------
            if s_id != '-':
                try:
                    service_results = db.session.query(service_table).filter(service_table.service_id == s_id).first()
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query service). Time: {datetime.now()}. Exception: {e}\n')
                    if "name" in request.referrer:
                        return redirect(url_for("repair_bp.repair_orders"))
                    return redirect(url_for("repair_bp.repair_orders"))

                description += "Service: "+str(service_results.name) + '\n'
                description += "Beschreibung: " + str(service_results.description) + '\n'
                description += "Servicepreis: " + str(service_results.price).replace('.', ',') + ' €' +'\n\n'
                service_price = service_results.price
            else:
                service_price = 0

            #Reparatur----------------------------------
            if r_id != '-':
                try:
                    repair_results = db.session.query(repair_table).filter(repair_table.repair_id == r_id).first()
                    o_r_id = db.session.query(item_table.id_repair).filter(item_table.item_id == i_id).first().id_repair
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query repair/ o_r_id). Time: {datetime.now()}. Exception: {e}\n')
                    if "name" in request.referrer:
                        return redirect(url_for("repair_bp.repair_orders"))
                    return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

                if str(o_r_id) != str(r_id) :
                    flash("KRITISCHER LOGIK FEHLER, repair_order.id_item != item.item_id (mapped to repair). Bitte melden.",'danger')
                    if "name" in request.referrer:
                        return redirect(url_for("repair_bp.repair_orders"))
                    return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

                description += "Reparatur-ID: " + str(repair_results.repair_id) + '\n'
                stmt = (f'''SELECT category.superior_category, category.name, item.name FROM spare_part
                            INNER JOIN item on spare_part.id_item = item.item_id 
                            INNER JOIN category on category.category_id = item.id_category 
                            WHERE spare_part.id_repair = {r_id};''')
                try:
                    spare_part_results = db.session.execute(stmt).fetchall()
                    db.session.commit()
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item). Time: {datetime.now()}. Exception: {e}\n')
                    if "name" in request.referrer:
                        return redirect(url_for("repair_bp.repair_orders"))
                    return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

                description += "Ersatzteile:"
                if spare_part_results is None:
                    description += '-\n'
                for spare_part in spare_part_results:
                    for s in spare_part:
                        description += str(s) + ', '
                description += '\n\n'

                if repair_results.price is None:
                    description += "Reparaturpreis: nicht angegeben" + '\n'
                else:
                    r_price = str(repair_results.price).replace('.',',')
                    description += "Reparaturpreis: " + r_price + ' €'+'\n'

            description += '\n----------------------------------\n'

            description += "Auftrag abgeschlossen durch: " + current_user.username + '\n'
            description += "Kommentar: " + request.form.get('description') + '\n'
            description += "Gesamtpreis: " + str(add_price).replace('.', ',') + ' €' + '\n'

            price = Decimal(add_price)

            if request.form.get("automatic_email") == 'on':
                try:
                    send_mail_to_customer(customer_results.name)
                except Exception as e:
                    flash("Auftrag konnte nicht abgeschlossen werden."+str(e), 'danger')
                    if "name" in request.referrer:
                        return redirect(url_for("repair_bp.repair_orders"))
                    return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            try:
                sale = sale_table(price=price, description=description, id_created_by=current_user.user_id)
                db.session.add(sale)
                db.session.flush()
                sa_id = sale.sale_id

                stmt = update(repair_order_table).where(repair_order_table.repair_order_id == o_id).values(
                    state='abgeschlossen', id_sale=sa_id, id_edited_by=current_user.user_id, delivery_date=now)

                db.session.execute(stmt)

                stmt = update(item_table).where(item_table.item_id == i_id).values(id_sale=sa_id)

                db.session.execute(stmt)

                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(f"Multiple transactions in repair_order failed (finish order) on {request.path}. Time: {now}. Exception: {e}\n')")
                flash(f"Auftrag konnte nicht abgeschlossen werden. -> Logfile: {now}", 'danger')
                if "name" in request.referrer:
                    return redirect(url_for("repair_bp.repair_orders"))
                return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

            flash(f"Der Auftrag (ID: {o_id}) wurde abgeschlossen.", 'success')
            if "name" in request.referrer:
                return redirect(url_for("repair_bp.repair_orders"))
            return redirect(url_for("repair_bp.repair_orders", page=session.get('last_repair_order_page')))

    if "name" in request.args:
        if request.args.get('name') != '':
            try:
                dict_list_open_orders, open_orders_total = get_repair_orders_dict_list(None, request.args.get('name'), 0, None, None)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("home_bp.dashboard"))

            if dict_list_open_orders != 0:
                return render_template("repair_orders.html", last_name = request.args.get('name'), open_orders_list=dict_list_open_orders)
            else:
                flash("Es wurde kein passender Auftrag gefunden.", 'info')
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

    if "id" in request.args:
        if request.args.get('id') != '':

            id = request.args.get('id')
            id = id.lower()
            id= id.replace(" ", "")

            stmt = f'''SELECT repair_order_id from repair_order WHERE repair_order.repair_order_id LIKE '%{id}%';'''
            try:
                o_id = db.session.execute(stmt).first()
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash("Fehler bei der Suche nach dem Auftrag.", 'danger')
                return redirect(url_for('repair_bp.repair_orders', page=session.get('last_repair_order_page')))

            if o_id is None:
                flash("Es wurde kein Auftrag mit dieser ID gefunden.", 'info')
            else:
                return redirect(url_for('repair_bp.repair_orders_i', o_id=o_id.repair_order_id))


    per_page = 5
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        dict_list_open_orders, open_orders_total = get_repair_orders_dict_list(None, None, 0, per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(dict_list_open_orders)} </b>  von <b class=\"bg-white\"> {open_orders_total} </b>."
    pagination_open = Pagination(page=page, total=open_orders_total, per_page=per_page, offset=offset, record_name='Aufträge',
                            display_msg=msg, css_framework='bootstrap5')

    #sort by date:
    #print(sorted(dict_list_open_orders, key=lambda i: i['AuftragDatum']))
    return render_template("repair_orders.html", last_name=None, open_orders_list=dict_list_open_orders, pagination_open = pagination_open)


@repair_bp.route('/repair_orders_finished', methods=['GET'])
@login_required
def repair_orders_finished():

    if "name" in request.args:
        if request.args.get('name') != '':
            try:
                dict_list_open_orders, open_orders_total = get_repair_orders_dict_list(None, request.args.get('name'), 1, None, None)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("home_bp.dashboard"))
            if dict_list_open_orders != 0:
                return render_template("repair_orders_finished.html", last_name = request.args.get('name'), finished_orders_list=dict_list_open_orders)
            else:
                flash("Es wurde kein passender Auftrag gefunden.", 'info')
                return redirect(url_for('repair_bp.repair_orders_finished'))

    if "id" in request.args:
        if request.args.get('name') != '':

            #check whether order exists before calling function:
            try:
                exists=db.session.query(repair_order_table).filter(repair_order_table.repair_order_id == request.args.get('id')).first()
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                flash("Suche nach Auftrag fehlgeschlagen.", 'danger')
                return redirect(url_for('repair_bp.repair_orders_finished'))

            if exists is None:
                flash("Es wurde kein passender Auftrag gefunden.", 'info')
                return redirect(url_for('repair_bp.repair_orders_finished'))

            try:
                dict_list_open_orders, open_orders_total = get_repair_orders_dict_list(request.args.get('id'), None, 1, None, None)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("home_bp.dashboard"))

            return render_template("repair_orders_finished.html", last_name = request.args.get('name'), finished_orders_list=dict_list_open_orders)


    per_page = 5
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        dict_list_finished_orders, finished_orders_total = get_repair_orders_dict_list(None, None, 1, per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(dict_list_finished_orders)} </b>  von <b class=\"bg-white\"> {finished_orders_total} </b>."
    pagination_finished = Pagination(page=page, total=finished_orders_total, per_page=per_page, offset=offset,
                                     record_name='Aufträge',
                                     display_msg=msg, css_framework='bootstrap5', show_single_page=False)

    return render_template("repair_orders_finished.html", last_name=None, finished_orders_list=dict_list_finished_orders,
                           pagination_finished=pagination_finished)

#MAIN/BASIC+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

@repair_bp.route('/repair_entry/<int:idd>', methods=['GET', 'POST'])
@login_required
def repair_entry(idd):

    try:
        not_available = check_item_deleted_or_sold_or_in_repair(idd)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    if not_available:
        flash("Das Item wurde bereits verkauft, existiert nicht mehr oder besitzt bereits einen Reparatur-Eintrag.", 'info')
        return redirect(url_for('inventory_bp.products'))

    if request.method == "POST":
        try:
            r_id = add_repair(idd)
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Reparatur Eintrag konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("repair_bp.repair_entry", idd=idd))

        return redirect(url_for('repair_bp.repair_details', r_id=r_id))

    #redirect
    return render_template("repair_entry.html")


@repair_bp.route('/repair_details/<int:r_id>', methods=['GET', 'POST'])
@login_required
def repair_details(r_id):

    try:
        repair_exists = db.session.query(repair_table.repair_id).filter(repair_table.repair_id == r_id).first()
        item_id_check = db.session.query(item_table.item_id).filter(item_table.id_repair == r_id).first()
    except SQLAlchemyError as e:
        flash(f' Reparatur Details konnten nicht geladen werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("home_bp.dashboard", r_id=r_id))

    if repair_exists is None:
        flash("Der Reparatur-Eintrag existiert nicht.", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    if 'redirect_finished_order' in request.args:
        return redirect(url_for('repair_bp.repair_orders_finished', id=request.args.get('redirect_finished_order')))

    if request.method == "POST":

        try:
            not_available = check_item_deleted_or_sold(item_id_check.item_id)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        if not_available:
            flash("Bearbeitung des Eintrages ist nicht möglich, da das Item verkauft oder gelöscht wurde.", 'danger')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        if "new_repair_description" in request.form:
            price = request.form.get('new_repair_price')
            if price == '':
                price = None
            else:
                price = price.replace(',', '.')
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(price=price,
                description=request.form.get('new_repair_description'), edit_date=datetime.now(), id_edited_by=current_user.user_id)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Änderungen konnten nicht gespeichert werden (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')

                return redirect(url_for("repair_bp.repair_details", r_id=r_id))
            flash("Änderungen wurden gepspeichert.", 'success')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        if request.form.get("delete_sp_only") is not None:

            try:
                not_available = check_spare_part_not_available(request.form.get("delete_sp_only"))
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            if not_available:
                flash("Das Ersatzteil konnte nicht gelöscht werden, z. B. da es durch einen anderen Nutzer auf 'vorhanden' gesetzt wurde.", 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                delete_spare_part(request.form.get("delete_sp_only"))
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                update_repair_edit(r_id, current_user.user_id)
            except Exception as e:
                flash(str(e),'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            flash("Ersatzteil wurde aus der Reparatur entfernt.", 'success')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        if request.form.get("delete_sp_or_item_or_both") is not None:
            sp_id = request.form.get('delete_sp_or_item_or_both')

            #todo: no rollback no mercy....

            if request.form.get("delete_item") == '1':
                try:
                    i_id = db.session.query(spare_part_table.id_item).filter(spare_part_table.spare_part_id == sp_id).first()
                    rep_id = db.session.query(item_table.id_repair).filter(item_table.item_id == i_id.id_item).first()
                except SQLAlchemyError as e:
                    flash(f' Item konnte nicht gelöscht werden (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                    app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

                #if spare part has repair entry -> return
                if rep_id.id_repair:
                    flash(f"Das Ersatzteil besitzt einen Reparatur Eintrag und muss über die Item Ansicht gelöscht werden.", 'danger')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

                #delete item
                try:
                    db.session.query(item_table).filter(item_table.item_id == i_id.id_item).delete()
                except Exception as e:
                    db.session.rollback()
                    flash(f' Ersatzteil konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                delete_spare_part(sp_id)
            except Exception as e:
                db.session.rollback()
                flash(f' Ersatzteil konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}','danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                update_repair_edit(r_id, current_user.user_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            flash("Einträge wurden gelöscht.", 'success')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        #add new spare part as existing item, or link existing spare part to item
        if request.form.get("item_id") is not None:

            if request.form.get("sp_id"):
                try:
                    not_available = check_spare_part_not_available(request.form.get('sp_id'))
                except Exception as e:
                    flash(str(e), 'danger')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

                if not_available:
                    flash("Das Ersatzteil konnte nicht mit einem Item verknüpft werden, z. B. da es durch einen anderen Nutzer auf 'vorhanden' gesetzt wurde.",
                        'danger')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            #state of existing spare_part is set to "vorhanden" -> set spare_part.id_item
            if request.form.get("referrer_is_state_change") is not None:

                stmt = update(spare_part_table).where(spare_part_table.spare_part_id == request.form.get('sp_id')).values(
                    id_item=request.form.get('item_id'), state="vorhanden")
                try:
                    db.session.execute(stmt)
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                    app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            #new spare_part, already existing is chosen from inventory -> create new sp with id_item already set
            else:
                #referrer => add new spare part
                sp = spare_part_table(id_item=request.form.get("item_id"), state='vorhanden', id_repair=r_id)
                try:
                    db.session.add(sp)
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash(f' Ersatzteil konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                    app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                update_repair_edit(r_id, current_user.user_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            flash("Änderungen gespeichert.", 'success')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

        #add spare part only
        if request.form.get("add_spare_part") is not None:
            price = request.form.get("new_spare_part_price")
            if price == '':
                sp = spare_part_table(name=request.form.get("new_spare_part_name"),
                                      description=request.form.get("new_spare_part_description"),
                                      state=request.form.get("new_spare_part_state"),
                                      vendor=request.form.get("new_spare_part_vendor"), id_repair=r_id)
            else:
                sp = spare_part_table(name=request.form.get("new_spare_part_name"),
                                      description=request.form.get("new_spare_part_description"),
                                      state=request.form.get("new_spare_part_state"),
                                      price=request.form.get("new_spare_part_price").replace(',', '.'),
                                      vendor=request.form.get("new_spare_part_vendor"), id_repair=r_id)

            try:
                db.session.add(sp)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Ersatzteil konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            try:
                update_repair_edit(r_id, current_user.user_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_details", r_id=r_id))

            flash("Ersatzteil wurde hinzugefügt.", 'success')
            return redirect(url_for("repair_bp.repair_details", r_id=r_id))

    #check (and change) repair state depending on spare_part states
    try:
        check_repair_state(r_id)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard", r_id=r_id))

    #repair details dictionary:
    try:
        item_results = db.session.query(item_table.item_id, item_table.id_sale).filter(item_table.id_repair == r_id).first()
        results_repair = db.session.query(repair_table.repair_id, repair_table.state, repair_table.description, repair_table.price).filter(repair_table.repair_id == r_id).first()
        results_repair_order = db.session.query(repair_order_table.repair_order_id, repair_order_table.state).join(repair_table).filter(
                                                repair_table.repair_id == r_id).first()
    except SQLAlchemyError as e:
        flash(f' Reparatur Details konnten nicht geladen werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("home_bp.dashboard", r_id=r_id))

    price = results_repair.price
    if price:
        price = str(price).replace('.',',')
    if results_repair_order is None:
        order_id = '-'
        repair_details = {
            "ID": results_repair.repair_id,
            "Status": results_repair.state,
            "Fehlerbeschreibung": results_repair.description,
            "Preis": price,
            "Auftrags-ID": '-'
        }

    else:
        order_id = results_repair_order.repair_order_id

        repair_details = {
            "ID": results_repair.repair_id,
            "Status": results_repair.state,
            "Fehlerbeschreibung": results_repair.description,
            "Preis": price,
            "Auftrags-ID": order_id,
            "Auftrags-Status": results_repair_order.state
        }

    #spare parts dictionary list:

    #HOW THE ACTUAL FUCK DID THE FOLLOWING LINE GET HERE ??! D: 31??!
    #i_id = (db.session.query(spare_part_table.id_item).filter(spare_part_table.spare_part_id==31).first()).id_item
    try:
        results_spare_parts = db.session.query(spare_part_table).filter(spare_part_table.id_repair == r_id).all()
    except SQLAlchemyError as e:
        flash(f' Reparatur Details konnten nicht geladen werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("home_bp.dashboard", r_id=r_id))

    spare_parts_dict_list = []
    for r in results_spare_parts:

        price = r.price
        if price:
            price = str(price).replace('.', ',')

        if r.id_item is not None:
            try:
                r_name = db.session.query(category_table.superior_category, category_table.name, item_table.name.label('i_name')).join(item_table).filter(item_table.item_id == r.id_item).first()
            except SQLAlchemyError as e:
                flash(f' Reparatur Details konnten nicht geladen werden (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("home_bp.dashboard", r_id=r_id))

            sp = {
                "ItemID": r.id_item,
                "Name": r_name.superior_category + ' ' + r_name.name + ' ' + r_name.i_name,
                "Preis": price,
                "Bestellt bei": r.vendor,
                "Beschreibung": r.description,
                "Status": r.state,
                "ID": r.spare_part_id
            }
            spare_parts_dict_list.append(sp)
        else:
            sp = {
                "ItemID": None,
                "Name": r.name,
                "Preis": price,
                "Bestellt bei": r.vendor,
                "Beschreibung": r.description,
                "Status": r.state,
                "ID": r.spare_part_id
            }
            spare_parts_dict_list.append(sp)

    return render_template("repair_details.html", item_id=item_results.item_id, sale_id=item_results.id_sale, repair_details=repair_details, spare_parts=spare_parts_dict_list)


@repair_bp.route('/repairs_internal', methods=['GET'])
@login_required
def repairs_internal():

    if not "repairs_internal" in request.referrer or "repairs_internal_finished" in request.referrer:
        if 'page' not in request.args:
            #wenn das page cookie noch nicht gesetzt ist, wird es Seite 1
            if session.get('last_repairs_internal_page'):
                return redirect(url_for('repair_bp.repairs_internal', page=session.get('last_repairs_internal_page')))
    else:
         if 'page' not in request.args:
            session['last_repairs_internal_page'] = 1
         else:
             session['last_repairs_internal_page'] = request.args.get('page')

    per_page = 6
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        internal_repairs_open, internal_repairs_open_total = get_internal_repair_dict(0, per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(internal_repairs_open)} </b>  von <b class=\"bg-white\"> {internal_repairs_open_total} </b>."
    pagination = Pagination(page=page, total=internal_repairs_open_total, per_page=per_page, offset=offset, record_name='Interne Reparaturen',
                            display_msg=msg, css_framework='bootstrap5')

    return render_template("repairs_internal.html", repairs_open=internal_repairs_open, pagination=pagination)


@repair_bp.route('/repairs_internal_finished', methods=['GET'])
@login_required
def repairs_internal_finished():

    per_page = 6
    page = request.args.get(get_page_parameter(), type=int, default=1)
    offset = (page - 1) * per_page

    try:
        internal_repairs_finished, internal_repairs_finished_total = get_internal_repair_dict(1, per_page, offset)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    msg = f"Einträge <b class=\"bg-white\"> {offset + 1}  bis {offset + len(internal_repairs_finished)} </b>  von <b class=\"bg-white\"> {internal_repairs_finished_total} </b>."
    pagination = Pagination(page=page, total=internal_repairs_finished_total, per_page=per_page, offset=offset, record_name='Kunden',
                            display_msg=msg, css_framework='bootstrap5')

    return render_template("repairs_internal_finished.html", repairs_finished=internal_repairs_finished, pagination=pagination)


@repair_bp.route('/spare_part_edit/<int:s_id>', methods=['GET', 'POST'])
@login_required
def spare_part_edit(s_id):

    try:
        sp_result = db.session.query(spare_part_table).filter(spare_part_table.spare_part_id == s_id).first()
        item_check = db.session.query(item_table.id_sale).filter(item_table.id_repair == sp_result.id_repair).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        flash(f"Ersatzteil Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    try:
        not_available_sp = check_spare_part_not_available(s_id)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    if not_available_sp:
        flash("Das Ersatzteil existiert nicht oder darf nicht bearbeitet werden.", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    if item_check.id_sale is not None:
        flash("Das Ersatzteil kann nicht bearbeitet werden, da das zu reparierende Item verkauft wurde.", 'danger')
        return redirect(url_for("home_bp.dashboard"))

    if request.method == "POST":
        price = request.form.get("edit_spare_part_price")
        if price == '':
            stmt = update(spare_part_table).where(spare_part_table.spare_part_id == s_id).values(
                name=request.form.get("edit_spare_part_name"),
                vendor=request.form.get("edit_spare_part_vendor"),
                description=request.form.get("edit_spare_part_description")
            )
        else:
            stmt = update(spare_part_table).where(spare_part_table.spare_part_id == s_id).values(
                name=request.form.get("edit_spare_part_name"),
                vendor=request.form.get("edit_spare_part_vendor"),
                price=request.form.get("edit_spare_part_price").replace(',','.'),
                description=request.form.get("edit_spare_part_description")
            )

        try:
            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            flash(f"Änderungen konnten nicht gespeichert werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}",
                'danger')
            return redirect(url_for("repair_bp.spare_part_edit", s_id=s_id))


        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(url_for("repair_bp.repair_details", r_id=sp_result.id_repair))


    price= sp_result.price
    if price:
        price = str(price).replace('.',',')
    sp = {
        "name": sp_result.name,
        "price": price,
        "vendor": sp_result.vendor,
        "description": sp_result.description
    }

    return render_template("spare_part_edit.html", spare_part=sp)


@repair_bp.route('/repair_orders_i/<int:o_id>', methods=['POST', 'GET'])
@login_required
def repair_orders_i(o_id):

    try:
        not_available = check_repair_order_not_available(o_id)
    except Exception as e:
        flash(f' Fehler beim Abrufen des Auftrages. (SQLAlchemy QUERY error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))
    if not_available:
        flash("Auftrag wurde bereits abgeschlossen oder gelöscht.", 'danger')
        return redirect(url_for("repair_bp.repair_orders"))

    if request.method == "POST":

        if "new_repair_price" in request.form:
            price = request.form.get('new_repair_price')
            r_id = request.form.get('r_id')
            if price == '':
                price = None
            else:
                price = price.replace(',', '.')
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(price=price,
                                                                                     edit_date=datetime.now(),
                                                                                     id_edited_by=current_user.user_id)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Änderungen konnten nicht gespeichert werden (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))
            flash("Änderungen wurden gepspeichert.", 'success')
            return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

        #session['last_repair_order_page'] = request.args.get('page')

        if "new_order_description" in request.form:
            o_id = o_id

            stmt = (
                update(repair_order_table).where(repair_order_table.repair_order_id == o_id)).values(
                id_edited_by=current_user.user_id, edit_date=datetime.now(), description=request.form.get("new_order_description")
            )
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Auftragsbeschreibung konnte nicht angepasst werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            flash("Auftragsbeschreibung wurde angepasst.", 'success')
            return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

        if "add_order_description" in request.form:
            o_id = request.form.get("order_id")

            stmt = (
                update(repair_order_table).where(repair_order_table.repair_order_id == o_id)).values(
                id_edited_by=current_user.user_id, edit_date=datetime.now(), description=request.form.get("add_order_description")
            )
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Auftragsbeschreibung konnte nicht hinzugefügt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            flash("Auftragsbeschreibung wurde hinzugefügt.", 'success')
            return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))


        if "add_repair_entry" in request.form:

            try:
                r_id = add_repair(request.form.get("item_id"))
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))
            stmt = (
            update(repair_table).where(repair_table.repair_id == r_id)).values(
                id_repair_order=request.form.get("order_id"), id_edited_by=current_user.user_id)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Reparatur-Eintrag konnte nicht hinzugefügt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            flash("Reparatur-Eintrag  wurde hinzugefügt.", 'success')
            return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

        #repair_order und item löschen
        if "delete_order" in request.form:

            i_id = request.form.get("delete_item")
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.query(repair_order_table).filter(repair_order_table.repair_order_id == o_id).delete()
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy DELETE exception on logout. Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Item und Auftrag konnten nicht gelöscht werden.(SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            flash(f"Das Item {i_id} und der Auftrag {o_id} wurden erfolgreich gelöscht.", 'success')
            return redirect(url_for("repair_bp.repair_orders"))

        if "finish_order" in request.form:

            #finish order:
            add_price = request.form.get("add_price")
            if add_price is None or add_price == '':
                add_price = 0
            else:
                add_price = add_price.replace(',','.')

            s_id = request.form.get("service_id")
            c_id = request.form.get("customer_id")
            r_id = request.form.get("repair_id")

            now = datetime.now()

            try:
                i_id = db.session.query(repair_order_table.id_item).filter(repair_order_table.repair_order_id == o_id).first().id_item
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item ID). Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            #Auftrag-------------------------------------
            try:
                results_repair_order = db.session.query(repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query repair_order). Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            description = "Abgeschlossener Auftrag - ID:" +str(o_id) + '\n\n Start-Datum: '+str(results_repair_order.issue_date) + '\n Liefer-Datum: '+ str(now) +'\n'
            description += "Beschreibung: "+str(results_repair_order.description) +'\n\n'

            #Kunde-----------------------------------------------------------------------------------------------
            try:
                customer_results = db.session.query(customer_table).filter(customer_table.customer_id == c_id).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query customer). Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            description += "Kunde: " + str(customer_results.name)+'\n\n'

            #Item----------------------------------------
            try:
                item_results = db.session.query(item_table.name, item_table.serial_number, item_table.description, item_table.id_category).filter(item_table.item_id==i_id).first()
                category_results = db.session.query(category_table.superior_category, category_table.name, category_table.spare_part_for, category_table.accessory_for).filter(
                    category_table.category_id == item_results.id_category).first()
            except SQLAlchemyError as e:
                flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item/Category). Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            description += "Item -ID: "+str(i_id)+' , Kategorie:' + str(category_results.spare_part_for) + str(category_results.accessory_for) + ' ' + str(category_results.superior_category) + ' ' + str(category_results.name) +'\n'
            description += "Bezeichnung: " + str(item_results.name) +'\n'
            description += "Seriennummer: " + str(item_results.serial_number) + '\n'
            description += "Beschreibung: " + str(item_results.description) +'\n\n'

            #service-------------------------------------
            if s_id != '-':
                try:
                    service_results = db.session.query(service_table).filter(service_table.service_id == s_id).first()
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query service). Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

                description += "Service: "+str(service_results.name) + '\n'
                description += "Beschreibung: " + str(service_results.description) + '\n'
                description += "Servicepreis: " + str(service_results.price).replace('.', ',') + ' €' +'\n\n'
                service_price = service_results.price
            else:
                service_price = 0

            #Reparatur----------------------------------
            if r_id != '-':
                try:
                    repair_results = db.session.query(repair_table).filter(repair_table.repair_id == r_id).first()
                    o_r_id = db.session.query(item_table.id_repair).filter(item_table.item_id == i_id).first().id_repair
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query repair/ o_r_id). Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

                if str(o_r_id) != str(r_id) :
                    flash("KRITISCHER LOGIK FEHLER, repair_order.id_item != item.item_id (mapped to repair). Bitte melden.",'danger')
                    return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

                description += "Reparatur-ID: " + str(repair_results.repair_id) + '\n'
                stmt = (f'''SELECT category.superior_category, category.name, item.name FROM spare_part
                            INNER JOIN item on spare_part.id_item = item.item_id 
                            INNER JOIN category on category.category_id = item.id_category 
                            WHERE spare_part.id_repair = {r_id};''')
                try:
                    spare_part_results = db.session.execute(stmt).fetchall()
                    db.session.commit()
                except SQLAlchemyError as e:
                    flash(f' Auftrag konnte nicht abgeschlossen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (query Item). Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

                description += "Ersatzteile:"
                if spare_part_results is None:
                    description += '-\n'
                for spare_part in spare_part_results:
                    for s in spare_part:
                        description += str(s) + ', '
                description += '\n\n'

                if repair_results.price is None:
                    description += "Reparaturpreis: nicht angegeben" + '\n'
                else:
                    r_price = str(repair_results.price).replace('.',',')
                    description += "Reparaturpreis: " + r_price + ' €'+'\n'

            description += '\n----------------------------------\n'

            description += "Auftrag abgeschlossen durch: " + current_user.username + '\n'
            description += "Kommentar: " + request.form.get('description') + '\n'
            description += "Gesamtpreis: " + str(add_price).replace('.', ',') + ' €' + '\n'

            price = Decimal(add_price)

            if request.form.get("automatic_email") == 'on':
                try:
                    send_mail_to_customer(customer_results.name)
                except Exception as e:
                    flash("Auftrag konnte nicht abgeschlossen werden."+str(e), 'danger')
                    return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            try:
                sale = sale_table(price=price, description=description, id_created_by=current_user.user_id)
                db.session.add(sale)
                db.session.flush()
                sa_id = sale.sale_id

                stmt = update(repair_order_table).where(repair_order_table.repair_order_id == o_id).values(
                    state='abgeschlossen', id_sale=sa_id, id_edited_by=current_user.user_id, delivery_date=now)

                db.session.execute(stmt)

                stmt = update(item_table).where(item_table.item_id == i_id).values(id_sale=sa_id)

                db.session.execute(stmt)

                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(f"Multiple transactions in repair_order failed (finish order) on {request.path}. Time: {now}. Exception: {e}\n')")
                flash(f"Auftrag konnte nicht abgeschlossen werden. -> Logfile: {now}", 'danger')
                return redirect(url_for("repair_bp.repair_orders_i", o_id=o_id))

            flash(f"Der Auftrag (ID: {o_id}) wurde abgeschlossen.", 'success')
            return redirect(url_for("repair_bp.repair_orders_finished"))


    try:
        dict_list_open_orders, open_orders_total = get_repair_orders_dict_list(o_id, None, 0, None, None)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for("home_bp.dashboard"))

    #sort by date:
    #print(sorted(dict_list_open_orders, key=lambda i: i['AuftragDatum']))
    return render_template("repair_orders_i.html", open_orders_list=dict_list_open_orders)
