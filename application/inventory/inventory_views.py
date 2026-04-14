import csv
import os

from flask import render_template, redirect, request, jsonify, Blueprint, url_for, flash, session, Response
from flask_login import login_required, current_user
from application import db, qr, app
from application.models import item_table, category_table, warehouse_table, User, sale_table, spare_part_table, \
    online_upload_table
from sqlalchemy import update
from application.inventory.inventory_func import query_specific_items, create_filter_stmt, \
    handle_category_input, build_content_html, get_single_item_description, set_sale_id_item, query_all_items, \
    get_item_details, get_item_warehouse_details, get_item_repair_info, get_item_availability, \
    check_item_deleted_or_sold_or_in_repair, set_upload_id_null, add_item_to_upload, query_specific_items_for_csv
from application.category.category_func import get_cat_id
from datetime import datetime
from decimal import Decimal
from application.repair.repair_func import add_repair
from application.warehouse.warehouse_views import get_warehouse_box_numbers
from application.upload.upload_func import add_upload, check_upload_availability
from sqlalchemy.exc import SQLAlchemyError


inventory_bp = Blueprint('inventory_bp', __name__, template_folder = 'templates', url_prefix='')

@inventory_bp.route('/base_id_input', methods=['GET'])
def base_id_input():
    i = request.args.get('item_id_input')
    i = i.replace(" ","")
    try:
        item_results = db.session.query(item_table).filter(item_table.item_id == i).first()
    except SQLAlchemyError as e:
        flash(f' Item Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(request.referrer)

    if item_results is not None:
        return redirect(url_for('inventory_bp.product_details', idd=i))
    else:
        flash(f'Item (ID: {i}) existiert nicht.', 'danger')
        return redirect(request.referrer)


@inventory_bp.route('/download', methods=['GET'])
def download():
    with open("inventory_export.csv", "r") as fp:
         test = fp.read()
    return Response(test, mimetype="text/csv")


#AJAX+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@inventory_bp.route('/change_item_amount_ajax', methods=['GET'])
def change_item_amount_ajax():
    now=datetime.now()
    i_id = request.args.get("item_id")
    stmt = (
        update(item_table).where(item_table.item_id == i_id).values(
            amount=request.args.get('amount'),
            edit_date=now,
            id_edited_by=current_user.user_id
        )
    )

    try:
        db.session.execute(stmt)
        db.session.commit()
    except Exception as e:
        app.logger.warning(str(e))
        return jsonify("error")
    return "success"


@inventory_bp.route('/create_csv_ajax', methods=['GET'])
def create_csv_ajax():
    filter_state = request.args.get('filter_state')
    filter_checked_by = request.args.get('filter_checked_by')
    filter_edited_by = request.args.get('filter_edited_by')

    chars = ['[', '"', ']']
    for c in chars:
        filter_checked_by = filter_checked_by.replace(c, '')
        filter_state = filter_state.replace(c, '')
        filter_edited_by = filter_edited_by.replace(c, '')

    filter_state = filter_state.split(',')
    filter_checked_by = filter_checked_by.split(',')
    filter_edited_by = filter_edited_by.split(',')

    if filter_state[0] == '':
        filter_state = None
    if filter_checked_by[0] == '':
        filter_checked_by = None
    if filter_edited_by[0] == '':
        filter_edited_by = None

    filter_stmt = create_filter_stmt(filter_state, filter_checked_by, filter_edited_by)
    sort_value = request.args.get('sort_value')
    name_search_val = request.args.get('name_search_val')
    sn_search_val = request.args.get('sn_search_val')

    try:
        col_labels, results = query_specific_items_for_csv(request.args.get('kat'), request.args.get('lvl1'),
                                                   request.args.get('lvl2'), request.args.get('lvl3'), filter_stmt,
                                                   sort_value, name_search_val, sn_search_val)
    except Exception as e:
        app.logger.warning(str(e))
        return jsonify("error")

    print(col_labels)

    with open('inventory_export.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=',')
        csvwriter.writerow(col_labels)
        for row in results:
            csvwriter.writerow(row)

    return jsonify("success")


@inventory_bp.route('/sort_ajax', methods=['GET'])
def sort_ajax():
    filter_state = request.args.get('filter_state')
    filter_checked_by = request.args.get('filter_checked_by')
    filter_edited_by = request.args.get('filter_edited_by')

    chars = ['[', '"', ']']
    for c in chars:
        filter_checked_by = filter_checked_by.replace(c, '')
        filter_state = filter_state.replace(c, '')
        filter_edited_by = filter_edited_by.replace(c, '')

    filter_state = filter_state.split(',')
    filter_checked_by = filter_checked_by.split(',')
    filter_edited_by = filter_edited_by.split(',')

    if filter_state[0] == '':
        filter_state = None
    if filter_checked_by[0] == '':
        filter_checked_by = None
    if filter_edited_by[0] == '':
        filter_edited_by = None

    filter_stmt = create_filter_stmt(filter_state, filter_checked_by, filter_edited_by)
    sort_value = request.args.get('sort_value')
    name_search_val = request.args.get('name_search_val')
    sn_search_val = request.args.get('sn_search_val')

    try:
        col_labels, results = query_specific_items(request.args.get('kat'), request.args.get('lvl1'),
                                                 request.args.get('lvl2'), request.args.get('lvl3'), filter_stmt, sort_value, name_search_val, sn_search_val)
    except Exception as e:
        app.logger.warning(str(e))
        return jsonify("error")

    html_str = build_content_html(col_labels, results)
    return html_str

#REVERSE CART-------------------------------------------------


@inventory_bp.route('/ajax_clear_sale_items', methods=['GET'])
def ajax_clear_sale_items():
    session.pop('reverse_cart')
    return jsonify("cleared!")


@inventory_bp.route('/ajax_clear_single_sale_item', methods=['GET'])
def ajax_clear_single_sale_item():
    try:
        session_list = session.get('reverse_cart')
    except Exception as e:
        app.logger(f"Failed to get reverse_cart content from Session. Exception on {request.path}. Time: {datetime.now()}. Exception: {e}")
        return jsonify("error")

    if not (request.args.get('id') in session_list):
        #it got cleared somewhere else
        return jsonify("item deleted")

    session_list.remove(str(request.args.get('id')))
    session['reverse_cart'] = session_list
    return jsonify("item deleted")


@inventory_bp.route('/ajax_get_sale_items', methods=['GET'])
def ajax_get_sale_items():
    try:
        ids = session.get('reverse_cart')
    except Exception as e:
        app.logger(f"Failed to get reverse_cart content from Session. Exception on {request.path}. Time: {datetime.now()}. Exception: {e}")
        return jsonify("error")

    if ids is None or not ids:
        return jsonify("empty")

    #check if item is already sold or delted -> remove ID from session
    for i in ids:
        try:
            not_available = check_item_deleted_or_sold_or_in_repair(i)
        except Exception as e:
            flash(str(e), 'danger')
            return jsonify("error")

        if not_available:
            ids.remove(str(i))
            session['reverse_cart'] = ids

    item_specs_dict_list = []
    for i in ids:
        try:
            item_cat_results = db.session.query(category_table.superior_category, category_table.name.label('c_name'),
                                            category_table.accessory_for, category_table.spare_part_for,
                                            item_table.name.label('i_name'), item_table.id_sale).join(item_table).filter(item_table.item_id == i).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')

        else:
            if item_cat_results.accessory_for != '':
                first = 'Zubehör - ' + str(item_cat_results.accessory_for) + ': '
            elif item_cat_results.spare_part_for != '':
                first = 'Ersatzteil - ' + str(item_cat_results.accessory_for) + ': '
            else:
                first = 'Gerät: '

            item_specs = {
                "ID": i,
                "first": first,
                "Top-Kategorie": item_cat_results.superior_category,
                "Kategorie": item_cat_results.c_name,
                "Bezeichnung": item_cat_results.i_name,
            }
            item_specs_dict_list.append(item_specs)

    return jsonify(item_specs_dict_list)


@inventory_bp.route('/ajax_add_sale_items', methods=['GET'])
def ajax_add_sale_items():

    ids = request.args.get('ids')

    chars = ['[', '"', ']']
    for c in chars:
        ids = ids.replace(c, '')

    ids = ids.split(',')

    if ids is None:
        return jsonify("empty")

    if ids[0] == '':
        return jsonify("empty")

    set_ids_check = set(ids)
    set_ids = set()

    #every item already deleted or sold doesn't get added to reverse cart
    while set_ids_check:
        i_id = set_ids_check.pop()

        try:
            not_available = check_item_deleted_or_sold_or_in_repair(i_id)
        except Exception as e:
            flash(str(e), 'danger')
            return jsonify("error")

        if not not_available:
            set_ids.add(i_id)

    if len(set_ids) == 0:
        return jsonify("empty")

    try:
        session_ids = session.get('reverse_cart')
    except Exception as e:
        app.logger(f"Failed to get reverse_cart content from Session. Exception on {request.path}. Time: {datetime.now()}. Exception: {e}")
        return jsonify("error")

    #if reverse cart is empty
    if not session_ids or session_ids[0] == '':
        session['reverse_cart'] = ids
    else:
        #remove duplicates:
        matches = set(session_ids) & set_ids
        set_ids.difference_update(matches)
        session_list = session_ids

        #cant add more than 100 items to session
        if len(set_ids)+len(session_list) >= 100:
            return jsonify("max_reached")

        session_list.extend(list(set_ids))

        #add to session
        session['reverse_cart'] = session_list

    return jsonify(str(len(ids)))

#ONLINE UPLOADS-----------------------------------------------------


@inventory_bp.route('/ajax_get_online_items', methods=['GET'])
def ajax_get_online_items():

    u_id = request.args.get('u_id')

    ids = [r.item_id for r in
                                    db.session.query(item_table.item_id).filter(
                                        item_table.id_online_upload == u_id)]

    if not ids:
        return jsonify("empty")

    item_specs_dict_list = []
    for i in ids:
        try:
            item_cat_results = db.session.query(category_table.superior_category, category_table.name.label('c_name'),
                                                category_table.accessory_for, category_table.spare_part_for,
                                                item_table.name.label('i_name'), item_table.id_sale).join(
                item_table).filter(item_table.item_id == i).first()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')

        else:
            if item_cat_results.accessory_for != '':
                first = 'Zubehör - ' + str(item_cat_results.accessory_for) + ': '
            elif item_cat_results.spare_part_for != '':
                first = 'Ersatzteil - ' + str(item_cat_results.accessory_for) + ': '
            else:
                first = 'Gerät: '

            item_specs = {
                "u_id": u_id,
                "ID": i,
                "first": first,
                "Top-Kategorie": item_cat_results.superior_category,
                "Kategorie": item_cat_results.c_name,
                "Bezeichnung": item_cat_results.i_name,
            }
            item_specs_dict_list.append(item_specs)

    return jsonify(item_specs_dict_list)


@inventory_bp.route('/ajax_clear_single_online_item', methods=['GET'])
def ajax_clear_single_online_item():

    i_id = request.args.get('i_id')
    u_id = request.args.get('u_id')

    try:
        upload_results = db.session.query(online_upload_table.id_shop_order).filter(
            online_upload_table.online_upload_id == u_id).first()

    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    if upload_results.id_shop_order is not None:
        return jsonify("not_available")

    try:
        item_results = db.session.query(item_table.item_id).filter(
            item_table.id_online_upload == u_id).all()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return jsonify("error")

    number_items = len(item_results)
    if number_items == 1:
        return jsonify("item_amount_error")


    try:
        set_upload_id_null(i_id)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify("error")

    return jsonify("item deleted")


@inventory_bp.route('/ajax_delete_multiple_items', methods=['GET'])
def ajax_delete_multiple_items():
    ids = request.args.get('ids')

    chars = ['[', '"', ']']
    for c in chars:
        ids = ids.replace(c, '')

    ids = ids.split(',')

    if ids is None:
        return jsonify("empty")

    if ids[0] == '':
        return jsonify("empty")

    for i in ids:
        try:
            db.session.execute(f'''delete item, repair from item LEFT JOIN repair ON item.id_repair = repair.repair_id WHERE item_id = {i};''')
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}')
            return jsonify('error')

    return jsonify(str(len(ids)))


#toDO: merge function to one again (since globals were removed) -> change in products

@inventory_bp.route('/ajax_responsive_categories_input', methods=['GET'])
def ajax_responsive_categories_input():

    #ersatzteile ajax responses----------------------------------------------------------------------------------------

    if request.args.get('kat') == 'ersatzteile':
        try:
            spare_parts = [r.spare_part_for for r in
                       db.session.query(category_table.spare_part_for).filter(category_table.spare_part_for != '',
                                                                              category_table.spare_part_for != 'None').distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (et 1). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(spare_parts)

    if not request.args.get('et') is None:
        try:
            sp_superior_cats = [r.superior_category for r in db.session.query(category_table.superior_category)
                .filter(category_table.spare_part_for == request.args.get('et')).distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (et 2). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(sp_superior_cats)

    if not request.args.get('et_top_kat') is None:
        try:
            sp_sub_cats = [r.name for r in db.session.query(category_table.name)
                .filter(category_table.superior_category == request.args.get('et_top_kat'),
                    category_table.spare_part_for == request.args.get('et_for_top_kat')).distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (et 3). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(sp_sub_cats)

    #zubehoer ajax responses----------------------------------------------------------------------------------------
    if request.args.get('kat') == 'zubehoer':
        try:
            accessories = [r.accessory_for for r in
                       db.session.query(category_table.accessory_for).filter(category_table.accessory_for != '',
                                                                             category_table.accessory_for != 'None').distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (zb 1). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(accessories)

    if not request.args.get('zb') is None:
        try:
            ac_superior_cats = [r.superior_category for r in db.session.query(category_table.superior_category)
                .filter(category_table.accessory_for == request.args.get('zb')).distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (zb 2). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(ac_superior_cats)

    if not request.args.get('zb_top_kat') is None:
        try:
            ac_sub_cats = [r.name for r in db.session.query(category_table.name)
                .filter(category_table.superior_category == request.args.get('zb_top_kat'),
                    category_table.accessory_for == request.args.get('zb_for_top_kat')).distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (zb 3). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(ac_sub_cats)

    #sonstiges ajax responses-------------------------------------------------------------------------------------------
    if request.args.get('kat') == 'anderes':
        try:
            o_superior_cats = [r.superior_category for r in
                           db.session.query(category_table.superior_category).filter(category_table.accessory_for == '',
                                                                                     category_table.spare_part_for == '').distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (a 1). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(o_superior_cats)

    if not request.args.get('a_top_kat') is None:
        try:
            o_sub_cats = [r.name for r in db.session.query(category_table.name)
                .filter(category_table.superior_category == request.args.get('a_top_kat'), category_table.accessory_for == '',
                    category_table.spare_part_for == '').distinct()]
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (a 2). Time: {datetime.now()}. Exception: {e}\n')
            return jsonify('error')
        return jsonify(o_sub_cats)

    app.logger.warning(f"{request.path} called without input. Logic error.")
    return 0


#PRODUCTSXMAINXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX


@inventory_bp.route('/products_warehouse_view', methods=['POST', 'GET'])
@login_required
def products_warehouse_view():
    return render_template("products_warehouse_view.html")


@inventory_bp.route('/products', methods=['POST', 'GET'])
@login_required
def products():

    if request.method == "POST":

        if "add_upload" in request.form:

            i_id = request.form.get("item_id")

            chars = ['[', '"', ']']
            for c in chars:
                i_id = i_id.replace(c, '')

            i_id = i_id.split(',')

            if i_id is None:
                flash("Keine Items ausgewählt!", 'danger')
                return redirect(url_for("inventory_bp.products"))
            if i_id[0] == '':
                flash("Keine Items ausgewählt!", 'danger')
                return redirect(url_for("inventory_bp.products"))

            try:
                u_id = add_upload()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f' {str(e)} -> Logfile Eintrag: {datetime.now()}',
                'danger')
                return redirect(url_for('inventory_bp.products'))

            if len(i_id) > 100:
                flash("Es können nicht mehr als 100 Items gleichzeitig hinzugefügt werden.", 'danger')
                return redirect(url_for("inventory_bp.products"))

            if len(i_id) == 1:
                try:
                    add_item_to_upload(i_id[0], u_id)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flash(str(e), 'danger')
                    return redirect(url_for("inventory_bp.products"))
                flash("Der Upload wurde erstellt und das Item hinzugefügt.", 'success')
                return redirect(url_for('inventory_bp.products'))
            else:
                for i in i_id:
                    try:
                        add_item_to_upload(i, u_id)
                    except Exception as e:
                        db.session.rollback()
                        flash(str(e), 'danger')
                        return redirect(url_for("inventory_bp.products"))
                try:
                    db.session.commit()
                except Exception as e:
                    app.logger.warning(f'SQLAlchemy commit failed {request.path} (upload_id, change item id_online_upload). Time: {datetime.now()}. Exception: {e}\n')
                    flash(f"Fehler beim Hinzufügen der Items. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}",
                        'danger')
                    return redirect(url_for("inventory_bp.products"))

            flash(f"Der Upload wurde erstellt und {len(i_id)} Items hinzugefügt.", 'success')
            return redirect(url_for('inventory_bp.products'))

        if "upload_id" in request.form:

            i_id = request.form.get("upload_item_id")

            u_id = request.form.get("upload_id")

            chars = ['[', '"', ']']
            for c in chars:
                i_id = i_id.replace(c, '')

            i_id = i_id.split(',')

            if i_id is None:
                flash("Keine Items ausgewählt!", 'danger')
                return redirect(url_for("inventory_bp.products"))
            if i_id[0] == '':
                flash("Keine Items ausgewählt!", 'danger')
                return redirect(url_for("inventory_bp.products"))

            if len(i_id) > 100:
                flash("Es können nicht mehr als 100 Items gleichzeitig hinzugefügt werden.", 'danger')
                return redirect(url_for("inventory_bp.products"))

            if len(i_id) == 1:
                try:
                    add_item_to_upload(i_id[0], u_id)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flash(str(e), 'danger')
                    return redirect(url_for("inventory_bp.products"))
                flash("Das Item wurde dem Upload hinzugefügt.", 'success')
                return redirect(url_for('inventory_bp.products'))
            else:
                for i in i_id:
                    try:
                        add_item_to_upload(i, u_id)
                    except Exception as e:
                        db.session.rollback()
                        flash(str(e), 'danger')
                        return redirect(url_for("inventory_bp.products"))
                try:
                    db.session.commit()
                except Exception as e:
                    app.logger.warning(f'SQLAlchemy commit failed {request.path} (upload_id, change item id_online_upload). Time: {datetime.now()}. Exception: {e}\n')
                    flash("Fehler beim Hinzufügen der Items. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                    return redirect(url_for("inventory_bp.products"))
                flash(f"{len(i_id)} Items wurden dem Upload hinzugefügt.", 'success')
                return redirect(url_for("inventory_bp.products"))

        if "sell_reverse_cart" in request.form:
            id_list = session.get('reverse_cart')

            if id_list and id_list != '':

                for i in id_list:

                    try:
                        not_available = check_item_deleted_or_sold_or_in_repair(i)
                    except Exception as e:
                        flash(str(e), 'danger')
                        return redirect(url_for('inventory_bp.products'))

                    if not_available:
                        flash("Eines der Items existiert nicht mehr, wurde bereits verkauft, oder es wurde ein Reparatur Eintrag hinzugefügt. Bitte erneut ausführen.",
                            'danger')
                        return redirect(url_for('inventory_bp.products'))

                description = "Verkauf mehrerer Items:" + '\n\n'

                for i in id_list:
                    try:
                        description_item = get_single_item_description(i)
                    except Exception as e:
                        flash(str(e), 'danger')
                        return redirect(url_for('inventory_bp.products'))
                    description += description_item
                description += '\n\n----------------------------------\n'
                description += "Verkauf abgeschlossen durch: " + current_user.username + '\n'
                description += "Kommentar: " + request.form.get('description') + '\n\n'
                description += "Gesamtpreis: " + request.form.get('price') + ' €'

                try:
                    sale = sale_table(price=Decimal(request.form.get('price').replace(',', '.')), description=description, id_created_by=current_user.user_id)
                    db.session.add(sale)
                    db.session.flush()
                    sa_id = sale.sale_id
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash(f' Items konnten nicht dem Verkauf zugeordnet werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                    app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for('inventory_bp.products'))

                #toDO: try with rollback!!!
                for i in id_list:

                    try:
                        set_sale_id_item(i, sa_id)
                    except Exception:
                        flash(f'FATAL ERROR- Verkaufs Eintrag wurde angelegt, die Items konnten diesem jedoch nicht zugeordnet werden.' +
                            f' Manuelle Korrektur unbedingt notenwendig! -> Log: {datetime.now()}', 'danger')
                        app.logger.error(
                            f"FATAL ERROR - Verkaufs Eintrag wurde angelegt, die Items konnten diesem jedoch nicht zugeordnet werden. Sale ID: {sa_id}. Item IDs: {str(id_list)}")
                        return redirect(url_for('home_bp.dashboard'))

                flash(f'{len(id_list)} Items wurden dem Verkauf hinzugefügt. ({str(id_list)})', 'success')
                session.pop('reverse_cart')
                return redirect(url_for('inventory_bp.products'))
            else:
                flash('Keine Items für den Verkauf ausgewählt', 'danger')
                return redirect(url_for('inventory_bp.products'))

        if 'sell_single_item' in request.form:
            i_id = request.form.get('item_id')

            try:
                not_available = check_item_deleted_or_sold_or_in_repair(i_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for('inventory_bp.products'))

            if not_available:
                flash("Das Item existiert nicht mehr oder wurde bereits verkauft.",
                      'danger')
                return redirect(url_for('inventory_bp.products'))

            description = "Verkauf eines Items:" + '\n\n'

            try:
                description_item = get_single_item_description(i_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for('inventory_bp.products'))
            if description_item == "removed":
                flash("Item existiert nicht mehr.", 'danger')
                return redirect(url_for("inventory_bp.products"))

            description += description_item

            description += '\n\n----------------------------------\n'
            description += "Verkauf abgeschlossen durch: " + current_user.username + '\n'
            description += "Kommentar: " + request.form.get('description') + '\n\n'
            description += "Gesamtpreis: " + request.form.get('price') + ' €'

            #toDo: handle with rollback
            try:
                sale = sale_table(price=Decimal(request.form.get('price').replace(',','.')), description=description,
                                  id_created_by=current_user.user_id)
                db.session.add(sale)
                db.session.flush()
                sa_id = sale.sale_id

                #db.session.commit()
                set_sale_id_item(i_id, sa_id)

            except Exception as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy ADD OR UPDATE exception on {request.path} (sell single item). Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Item konnte dem Verkauf nicht hinzugefügt werden.(SQLAlchemy add(), update() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                return redirect(url_for("inventory_bp.products"))
            flash(f'Item (ID: {i_id}) wurden dem Verkauf hinzugefügt.', 'success')
            return redirect(url_for("inventory_bp.products"))

    #to display filters
    try:
        users = User.query.filter(User.username != 'deleted_user', User.username != 'automatic').all()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path} (users). Time: {datetime.now()}. Exception: {e}\n')
        flash(f' Fehler beim laden der Items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
        return redirect(url_for("home_bp.dashboard"))

    #add filter
    filter_state = request.form.getlist('filter_state')
    filter_checked_by = request.form.getlist('filter_checked_by')
    filter_edited_by = request.form.getlist('filter_edited_by')

    filter_stmt = create_filter_stmt(filter_state, filter_checked_by, filter_edited_by)

    try:
        et_content, et_header, zb_content, zb_header, sonst_content, sonst_header = query_all_items(filter_stmt, False)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    try:
        et_content_rep, et_header, zb_content_rep, zb_header, sonst_content_rep, sonst_header = query_all_items(filter_stmt, True)
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('home_bp.dashboard'))

    return render_template("products.html",
                           et_content=et_content, et_content_rep=et_content_rep, et_header=et_header, zb_content=zb_content,
                           zb_content_rep = zb_content_rep,
                           zb_header=zb_header,
                           sonst_content=sonst_content, sonst_content_rep=sonst_content_rep, sonst_header=sonst_header,
                           users=users,
                           thing='alle')


@inventory_bp.route('/product_details/<int:idd>', methods=['GET', 'POST'])
@login_required
def product_details(idd):
    qr_img = qr(f'https://imsserver.hopto.org/product_details/{idd}', box_size=10, border=5)

    #should be true if item is in repair and order
    dont_delete = False

    #prüfen ob das Item (z. B. durch einen anderen User) gelöscht wurde:
    try:
        item_exists = db.session.query(item_table).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("inventory_bp.products"))

    if item_exists is None:
        flash(f'Das Item existiert nicht.', 'danger')
        return redirect(url_for("inventory_bp.products"))


    if request.method == "POST":
        if "delete_inv_element" in request.form:

            try:
                rep_id = db.session.query(item_table.id_repair).filter(item_table.item_id == idd).first()
            except SQLAlchemyError as e:
                app.logger.warning(f"SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n")
                flash(f'Item konnte nicht gelöscht werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            spare_part_results = None
            if rep_id.id_repair:
                try:
                    spare_part_results = db.session.query(spare_part_table.spare_part_id, spare_part_table.id_item).filter(spare_part_table.id_repair == rep_id.id_repair).all()
                except SQLAlchemyError as e:
                    app.logger.warning(f"SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n")
                    flash(f'Item konnte nicht gelöscht werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    return redirect(url_for("inventory_bp.product_details", idd=idd))

                for spare_part in spare_part_results:
                    if spare_part.id_item:
                        flash("Item konnte nicht gelöscht werden. Es existiert ein Reparatur-Eintrag mit vorhandenen Ersatzteilen. Dies müssen zuvor manuell gelöscht werden.", 'danger')
                        return redirect(url_for("inventory_bp.product_details", idd=idd))

            try:
                if spare_part_results:
                    for spare_part in spare_part_results:
                        db.session.query(spare_part_table).filter(spare_part_table.spare_part_id == spare_part.spare_part_id).delete()
                db.session.execute(f'''delete item, repair from item LEFT JOIN repair ON item.id_repair = repair.repair_id
                                    WHERE item_id = {request.form.get('delete_inv_element')};''')
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Item konnte nicht gelöscht werden (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy DELETE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            if spare_part_results:
                flash(f"Item, Reparatur-Eintrag (ID: {rep_id.id_repair}) und {len(spare_part_results)} Ersatzteil-Einträge wurden gelöscht.", 'success')
            elif rep_id.id_repair:
                flash(f"Item und Reparatur-Eintrag (ID: {rep_id.id_repair}) wurden gelöscht.", 'success')
            else:
                flash("Item wurde gelöscht.", 'success')
            return redirect(url_for("inventory_bp.products"))

        if 'sell_single_item' in request.form:
            i_id = request.form.get('item_id')

            try:
                not_available = check_item_deleted_or_sold_or_in_repair(i_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            if not_available:
                flash("Das Item existiert nicht mehr oder wurde bereits verkauft.",
                      'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            description = "Verkauf eines Items:" + '\n\n'

            try:
                description_item = get_single_item_description(i_id)
            except Exception as e:
                flash(str(e), 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))
            if description_item == "removed":
                flash("Item existiert nicht mehr.", 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            description += description_item

            description += '\n\n----------------------------------\n'
            description += "Verkauf abgeschlossen durch: " + current_user.username + '\n'
            description += "Kommentar: " + request.form.get('description') + '\n\n'
            description += "Gesamtpreis: " + request.form.get('price') + ' €'


            try:
                sale = sale_table(price=Decimal(request.form.get('price').replace(',','.')), description=description,
                                  id_created_by=current_user.user_id)
                db.session.add(sale)
                db.session.flush()
                sa_id = sale.sale_id

                #db.session.commit()
                set_sale_id_item(i_id, sa_id)

            except Exception as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy ADD OR UPDATE exception on {request.path} (sell single item). Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Item konnte dem Verkauf nicht hinzugefügt werden.(SQLAlchemy add(), update() error) -> Logfile Eintrag: {datetime.now()}", 'danger')
                return redirect(url_for("inventory_bp.products"))
            flash(f'Item (ID: {i_id}) wurden dem Verkauf hinzugefügt.', 'success')
            return redirect(url_for("inventory_bp.product_details", idd=idd))

        if "add_upload" in request.form:

            i_id = request.form.get("item_id")

            if i_id is None:
                flash("Item ID is None ?!", 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            try:
                u_id = add_upload()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f' {str(e)} -> Logfile Eintrag: {datetime.now()}', 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            try:
                add_item_to_upload(i_id, u_id)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(str(e), 'danger')
                return redirect(url_for("inventory_bp.products"))
            flash("Upload wurde erstellt und das Item wurde hinzugefügt.", 'success')
            return redirect(url_for("inventory_bp.product_details", idd=idd))

        if "upload_id" in request.form:

            i_id = request.form.get("upload_item_id")

            u_id = request.form.get("upload_id")

            if i_id is None:
                flash("Item ID is None??", 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))

            try:
                add_item_to_upload(i_id, u_id)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(str(e), 'danger')
                return redirect(url_for("inventory_bp.product_details", idd=idd))
            flash("Das Item wurde dem Upload hinzugefügt.", 'success')
            return redirect(url_for("inventory_bp.product_details", idd=idd))

    try:
        item_details = get_item_details(idd)
    except Exception as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        return redirect(url_for("inventory_bp.products"))

    try:
        lager = get_item_warehouse_details(idd)
    except Exception as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        return redirect(url_for("inventory_bp.products"))

    try:
        repair_info = get_item_repair_info(idd)
    except Exception as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        return redirect(url_for("inventory_bp.products"))

    try:
        availability = get_item_availability(idd)
    except Exception as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(str(e))
        return redirect(url_for("inventory_bp.products"))

    return render_template("product_details.html", item_details=item_details, lager=lager,
                           repair_info=repair_info, qr_img=qr_img, availability=availability)


@inventory_bp.route('/product_edit/<int:idd>/<int:order>', methods=['GET', 'POST'])
@login_required
def product_edit(idd, order):
    now = datetime.now()

    if order==1:
        print("true")

    #prüfen ob das Item (z. B. durch einen anderen User) gelöscht wurde:
    try:
        item_exists = db.session.query(item_table).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        flash(
            f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("inventory_bp.products"))

    if item_exists is None:
        flash(f'Das Item existiert nicht.', 'danger')
        return redirect(url_for("inventory_bp.products"))

    if request.method == "POST":

        if "kategorie" in request.form:
            kat = request.form.get("kategorie")
            if kat == "anderes":
                try:
                    cat_id = get_cat_id(request.form.get("anderes_top_kat"), request.form.get("a_sub_kat"), '', '')
                except Exception as e:
                    flash(f"Kategorie konnte nicht gewechselt werden. {str(e)}")
                    return redirect(url_for("inventory_bp.product_edit", idd=idd))
            if kat == "ersatzteile":
                try:
                    cat_id = get_cat_id(request.form.get("ersatzteile_top_kat"), request.form.get("ersatzteile_sub_kat"), '', request.form.get("ersatzteile_et"))
                except Exception as e:
                    flash(f"Kategorie konnte nicht gewechselt werden. {str(e)}")
                    return redirect(url_for("inventory_bp.product_edit", idd=idd))
            if kat == "zubehoer":
                try:
                    cat_id = get_cat_id(request.form.get("zubehoer_top_kat"), request.form.get("zubehoer_sub_kat"), request.form.get("zubehoer_zb"), '')
                except Exception as e:
                    flash(f"Kategorie konnte nicht gewechselt werden. {str(e)}")
                    return redirect(url_for("inventory_bp.product_edit", idd=idd))

            stmt =(
                update(item_table).where(item_table.item_id == idd).values(
                    id_category=cat_id.category_id
                )
            )

            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path} (change category). Time: {datetime.now()}. Exception: {e}\n')
                flash(f"Kategorie konnte nicht gewechselt werden. {str(e)}")
                return redirect(url_for("inventory_bp.product_edit", idd=idd))

            return redirect(url_for("inventory_bp.product_edit", idd=idd))


        try:
            w_id = db.session.query(warehouse_table.warehouse_id)\
                .filter(warehouse_table.box_number == request.form.get('warehouse_box_number')).first()
        except SQLAlchemyError as e:
            flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("inventory_bp.product_details", idd=idd))
        if order==0:
            price = int(request.form.get('price_input').replace(',', ''))
        else:
            price=0
        if w_id is None or w_id == '':
            stmt_i = (
                update(item_table).where(item_table.item_id == idd).values(
                    name=request.form.get('bez_input'),
                    state=request.form.get('1_status'),
                    price=price,
                    description=request.form.get('description_input'),
                    serial_number = request.form.get('serial_number_input'),
                    edit_date=now,
                    id_edited_by=current_user.user_id)
            )

        else:
            stmt_i = (
                update(item_table).where(item_table.item_id == idd).values(
                    name=request.form.get('bez_input'),
                    state=request.form.get('1_status'),
                    price=price,
                    description=request.form.get('description_input'),
                    serial_number=request.form.get('serial_number_input'),
                    edit_date=now,
                    id_edited_by=current_user.user_id,
                    id_warehouse=w_id.warehouse_id)
            )

        try:
            db.session.execute(stmt_i)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Änderungen konnten nicht gespeichert werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("inventory_bp.products"))

        flash("Änderungen wurden gespeichert.", 'success')
        return redirect(f"/product_details/{idd}")

    try:
        cat = db.session.query(category_table.name, category_table.category_id).join(item_table)\
                                .filter(item_table.item_id == idd).first()

        cat_content = db.session.execute(f'''SELECT category.category_id, category.superior_category, 
                                            category.name, category.spare_part_for, 
                                            category.accessory_for
                                            FROM category WHERE category.category_id ='{cat.category_id}';''').first()

        item_content = db.session.execute(f'''SELECT item.item_id, item.name, item.serial_number, item.price, item.description,
                                            item.id_warehouse, item.state
                                            FROM item WHERE item.item_id='{idd}';''').first()
    except SQLAlchemyError as e:
        flash(f' Item-Details konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return redirect(url_for("inventory_bp.product_details", idd=idd))

    item_header = ['ID', 'Name', 'Seriennummer', 'Preis', 'Beschreibung', 'Lager-ID', 'Status']
    cat_header = ['Kategorie-ID', 'Kategorie', 'Bezeichnung', 'Ersatzteil von', 'Zubehör von']

    return render_template("product_edit.html", kat_bez=cat.name, kat_header=cat_header, kat_content=cat_content,
                           inv_header=item_header,
                           inv_content=item_content, warehouse_box_numbers=get_warehouse_box_numbers(), order=order)


#INPUTXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

#toDo save already typed values in local storage
@inventory_bp.route('/input_values', methods=['POST', 'GET'])
@login_required
def input_values():

    #inserts------------------------------------------------------------------------------------------------------------
    if request.method == "POST":

        anzahl = request.form.get('anzahl')

        try:
            cat_id = handle_category_input()
        except Exception as e:
            flash(str(e),'danger')
            return redirect(url_for('inventory_bp.input_values'))

        if cat_id == "empty":
            flash("Item konnte nicht hinzugefügt werden. Eine Kategorie Bezeichnung muss ausgewählt werden.", 'danger')
            return redirect(url_for('inventory_bp.input_values'))


        #ausgewählte Lagernummer
        w_id = request.form.get("warehouse_box_number")
        if w_id != '':
            try:
                w_id = db.session.query(warehouse_table.warehouse_id).filter(
                    warehouse_table.box_number == request.form.get('warehouse_box_number')).first()
            except SQLAlchemyError as e:
                flash(f' Item konnte nicht hinzugefügt werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("inventory_bp.input_values"))

        #add selected number of items with selected / created cat_id
        price=int(request.form.get('price').replace(',',''))
        if w_id is None or w_id == '':
            item = item_table(name=request.form.get('bez_input'),
                              serial_number = request.form.get('serial_number_input'),
                                           amount = anzahl,
                                           price=price,
                                           description=request.form.get('description_input'),
                                           internal = 1,
                                           state = request.form.get('status'),
                                           id_checked_by = current_user.user_id,
                                           id_category = cat_id.category_id)

        else:
            #for i in range(int(anzahl)):
            item = item_table(name=request.form.get('bez_input'),
                              serial_number=request.form.get('serial_number_input'),
                                      amount=anzahl,
                                      price=price,
                                      description=request.form.get('description_input'),
                                      internal=1,
                                      state=request.form.get('status'),
                                      id_checked_by=current_user.user_id,
                                      id_category=cat_id.category_id,
                                      id_warehouse = w_id.warehouse_id)


        try:
            db.session.add(item)
            db.session.flush()
            added_item_id = item.item_id
            db.session.commit()
            flash(f"Item ID:{added_item_id} wurde hinzugefügt.", 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Item(s) konnte(n) nicht hinzugefügt werden. (SQLAlchemy add_all() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD_ALL exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for('inventory_bp.input_values'))

    return render_template("input_values.html")

#INPUT for repair orders:

#INPUTXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

#toDo save already typed values in local storage
@inventory_bp.route('/input_values_external', methods=['POST', 'GET'])
@login_required
def input_values_external():

    origin = session.get('last_repair_input_page')

    #inserts------------------------------------------------------------------------------------------------------------
    if request.method == "POST":

        try:
            cat_id = handle_category_input()
        except Exception as e:
            flash(str(e),'danger')
            return redirect(url_for("repair_bp.repair_input_c", c_id=int(origin.split("/")[2])))

        if cat_id == "empty":
            flash("Item konnte nicht hinzugefügt werden. Eine Kategorie Bezeichnung muss ausgewählt werden.", 'danger')
            return redirect(url_for("repair_bp.repair_input_c", c_id=int(origin.split("/")[2])))


        #ausgewählte Lagernummer
        w_id = request.form.get("warehouse_box_number")
        if w_id != '':
            try:
                w_id = db.session.query(warehouse_table.warehouse_id).filter(
                    warehouse_table.box_number == request.form.get('warehouse_box_number')).first()
            except SQLAlchemyError as e:
                flash(f' Item konnte nicht hinzugefügt werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repair_input_c", c_id=int(origin.split("/")[2])))


        if w_id is None or w_id == '':
            i = item_table(name=request.form.get('bez_input'),
                           serial_number=request.form.get('serial_number_input'),
                           amount=1,
                           price=0,
                           description=request.form.get('description_input'),
                           internal= 0,
                           state=request.form.get('status'),
                           id_checked_by=current_user.user_id,
                           id_category=cat_id.category_id)
        else:
            i = item_table(name=request.form.get('bez_input'),
                           serial_number=request.form.get('serial_number_input'),
                           amount=1,
                           price=0,
                           description=request.form.get('description_input'),
                           internal=0,
                           state=request.form.get('status'),
                           id_checked_by=current_user.user_id,
                           id_category=cat_id.category_id,
                           id_warehouse=w_id.warehouse_id)

        try:
            db.session.add(i)
            db.session.flush()
            i_item_id = i.item_id
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Item konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            session['last_repair_input_page'] = url_for("repair_bp.repair_input_c", c_id=int(origin.split("/")[2]))
            return redirect(url_for("repair_bp.repair_input_c", c_id=int(origin.split("/")[2])))

        flash(f"Item (ID:{i_item_id}) wurde hinzugefügt.", 'success')
        session['last_repair_input_page'] = url_for("repair_bp.repair_input_c_i", c_id=int(origin.split("/")[2]), i_id=i_item_id)
        return redirect(url_for("repair_bp.repair_input_c_i", c_id=int(origin.split("/")[2]), i_id=i_item_id))

    return render_template("input_values_external.html")


#toDo save already typed values in local storage
@inventory_bp.route('/input_values_repairs_internal', methods=['POST', 'GET'])
@login_required
def input_values_repairs_internal():

    #inserts------------------------------------------------------------------------------------------------------------
    if request.method == "POST":

        try:
            cat_id = handle_category_input()
        except Exception as e:
            flash(str(e),'danger')
            return redirect(url_for("repair_bp.repairs_internal"))

        if cat_id == "empty":
            flash("Item konnte nicht hinzugefügt werden. Eine Kategorie Bezeichnung muss ausgewählt werden.", 'danger')
            return redirect(url_for("repair_bp.repairs_internal"))


        #ausgewählte Lagernummer
        w_id = request.form.get("warehouse_box_number")
        if w_id != '':
            try:
                w_id = db.session.query(warehouse_table.warehouse_id).filter(
                    warehouse_table.box_number == request.form.get('warehouse_box_number')).first()
            except SQLAlchemyError as e:
                flash(f' Item konnte nicht hinzugefügt werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
                    'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("repair_bp.repairs_internal"))

        price = int(request.form.get('price').replace(',', ''))

        if w_id is None or w_id == '':
            i = item_table(name=request.form.get('bez_input'),
                           serial_number=request.form.get('serial_number_input'),
                           price=price,
                           amount=1,
                           description=request.form.get('description_input'),
                           internal= 1,
                           state=request.form.get('status'),
                           id_checked_by=current_user.user_id,
                           id_category=cat_id.category_id)
        else:
            i = item_table(name=request.form.get('bez_input'),
                           serial_number=request.form.get('serial_number_input'),
                           price=price,
                           amount=1,
                           description=request.form.get('description_input'),
                           internal=1,
                           state=request.form.get('status'),
                           id_checked_by=current_user.user_id,
                           id_category=cat_id.category_id,
                           id_warehouse=w_id.warehouse_id)

        try:
            db.session.add(i)
            db.session.flush()
            i_item_id = i.item_id
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Item konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("repair_bp.repairs_internal"))

        try:
            r_id = add_repair(i_item_id)
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f' Reparatur Eintrag konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for("repair_bp.repairs_internal"))

        flash(f"Item (ID:{i_item_id}) wurde hinzugefügt und Reparatur (ID:{r_id} )wurde angelegt.", 'success')
        return redirect(url_for("repair_bp.repairs_internal"))

    return render_template("input_values_repairs_internal.html")