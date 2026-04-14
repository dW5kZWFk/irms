from flask import request, url_for, session
from flask_login import current_user
from application import db, app
from application.models import category_table, item_table, User, warehouse_table, repair_order_table, spare_part_table,\
    repair_table, sale_table, customer_table
from application.category.category_func import get_cat_id
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from babel.dates import format_datetime

from application.upload.upload_func import check_upload_availability


def add_item_to_upload(i_id, u_id):
    try:
        not_available = check_item_deleted_or_sold_or_in_repair(i_id)
    except Exception as e:
        raise Exception(f"Fehler beim hinzufügen des Items. {str(e)}")

    if not_available:
        raise Exception("Item(s) nicht mehr verfügbar.")

    try:
        not_available = check_upload_availability(u_id)
    except Exception as e:
        raise Exception(f"Fehler beim hinzufügen des Items. {str(e)}")

    if not_available:
        raise Exception("Der Upload ist nicht mehr verfügbar.")

    stmt = update(item_table).where(item_table.item_id == i_id).values(id_online_upload=u_id)
    try:
        db.session.execute(stmt)
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim hinzufügen des Items. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}')

    return None


def set_upload_id_null(i_id):
    stmt = update(item_table).where(item_table.item_id == i_id).values(
        id_online_upload=None)

    try:
        db.session.execute(stmt)
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (set_upload_id_null). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler beim ändern der Item-Online_upload ID.  {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return None


#or online
def check_item_deleted_or_sold(i_id):

    try:
        item_results = db.session.query(item_table.item_id, item_table.id_sale, item_table.id_online_upload).filter(item_table.item_id == i_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Prüfen der Item verfügbarkeit fehlgeschlagen. {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if item_results is None or item_results.id_sale is not None or item_results.id_online_upload is not None:
        return True
    return False


def check_item_deleted_or_sold_or_in_repair(i_id):

    try:
        item_results = db.session.query(item_table.item_id, item_table.id_sale, item_table.id_repair, repair_table.state, item_table.id_online_upload).join(repair_table, isouter=True).filter(item_table.item_id == i_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Prüfen der Item verfügbarkeit fehlgeschlagen. {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if item_results is None or item_results.id_sale is not None or item_results.id_online_upload is not None or (item_results.id_repair is not None and item_results.state != "abgeschlossen"):
        return True
    return False


#sale id for item and perhaps used spare parts in repair
def set_sale_id_item(i_id, sa_id):

    stmt = update(item_table).where(item_table.item_id == i_id).values(id_sale=sa_id)
    r_id = db.session.query(item_table.id_repair).filter(item_table.item_id == i_id).first()
    if r_id:

        sp_results = db.session.query(spare_part_table.id_item).filter(spare_part_table.id_repair == r_id.id_repair, spare_part_table.id_item != None).all()
        if sp_results:
            for i in sp_results:

                #toDo: recursion could be critical !!
                try:
                    set_sale_id_item(i.id_item, sa_id)
                except Exception as e:
                    raise Exception(f'{str(e)}')

    try:
        db.session.execute(stmt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in set_sale_id_item (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}')
    return 1


def get_single_item_description(i_id):

    description = ''

    try:
        item_results = db.session.query(item_table.name, item_table.serial_number, item_table.description, item_table.id_category).filter(
            item_table.item_id == i_id).first()
        if item_results is None:
            return "removed"
        category_results = db.session.query(category_table.superior_category, category_table.name,
                                            category_table.spare_part_for, category_table.accessory_for).filter(
            category_table.category_id == item_results.id_category).first()

    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_single_item_description (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')



    description += "Item -ID: " + str(i_id) + ' , Kategorie:' + str(category_results.spare_part_for) + str(
        category_results.accessory_for) + ' ' + str(category_results.superior_category) + ' ' + str(
        category_results.name) + '\n'
    description += "Bezeichnung: " + str(item_results.name) + '\n'
    description += "Seriennummer: " + str(item_results.serial_number) + '\n'
    description += "Beschreibung: " + str(item_results.description) + '\n\n'

    return description


def get_single_item_description_order(i_id):

    description = ''

    try:
        item_results = db.session.query(item_table.name, item_table.description, item_table.id_category).filter(
            item_table.item_id == i_id).first()
        category_results = db.session.query(category_table.superior_category, category_table.name,
                                            category_table.spare_part_for, category_table.accessory_for).filter(
            category_table.category_id == item_results.id_category).first()

    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(
            f' Fehler in get_single_item_description (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    description += f"{str(item_results.name)} "
    description += f'(Kategorie: {str(category_results.superior_category)}, {str(category_results.name)})'

    return description


#used in repair_input_c_i and repair_input_c_i_s
def get_single_item(i_id):

    try:
        cat = db.session.query(category_table).join(item_table).filter(item_table.item_id == i_id).first()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_single_item (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    #ersatzteile
    if cat.spare_part_for is not None and cat.spare_part_for != '' and cat.accessory_for is None or cat.accessory_for == '':

        try:
            i = db.session.query(item_table.item_id, category_table.spare_part_for, category_table.superior_category,
                             category_table.name.label('category_name'),
                             item_table.name.label('item_name')).join(category_table).filter(
                             item_table.item_id == i_id).first()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_single_item (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
        return i

    #zubehoer
    if cat.accessory_for is not None and cat.accessory_for != '' and cat.spare_part_for is None or cat.spare_part_for == '':

        try:
            i = db.session.query(item_table.item_id, category_table.accessory_for, category_table.superior_category,
                                 category_table.name.label('category_name'),
                                 item_table.name.label('item_name')).join(category_table).filter(
                                 item_table.item_id == i_id).first()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in get_single_item (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        return i

    #geräte
    try:
        i = db.session.query(item_table.item_id, category_table.superior_category,
                         category_table.name.label('category_name'),
                         item_table.name.label('item_name')).join(category_table).filter(
                         item_table.item_id == i_id).first()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in get_single_item (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')
    return i


#item should not be displayed when
#item is external
#item is sold
#item is in "spare_part" table
def query_specific_items(cat, sub_kat_lvl1, sub_kat_lvl2, sub_kat_lvl3, filter_stmt, sort_value, name_search_val, sn_search_val):

    search_stmt = ''
    if name_search_val is not None and name_search_val != '':
        search_value = name_search_val.lower()
        search_stmt += f'''AND LOWER(item.name) LIKE '%{search_value}%' '''

    if sn_search_val is not None and sn_search_val != '':
        search_value = sn_search_val.lower()
        search_stmt += f'''AND LOWER(item.serial_number) LIKE '%{search_value}%' '''

    order_stmt = ''
    if sort_value == 'name':
        order_stmt = 1
    elif sort_value == 'id':
        order_stmt = '''ORDER BY item.item_id'''
    elif sort_value == 'add_date':
        order_stmt = 'ORDER BY UNIX_TIMESTAMP(item.check_date) desc'
    elif sort_value == 'edit_date':
        order_stmt = 'ORDER BY UNIX_TIMESTAMP(item.edit_date) desc'
    else:
        #box_no
        order_stmt = 'ORDER BY warehouse.box_number desc'

    #name date id box_no
    if cat == 'zubehoer':

        if sub_kat_lvl2 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'

            stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.state, item.amount, item.price,
                        warehouse.box_number
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.accessory_for = '{sub_kat_lvl1}'
                        {search_stmt}
                        {order_stmt};''')
            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

            results = [list(i) for i in results]

            return col_labels, results

        if sub_kat_lvl3 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'

            stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, 
                        category.name, item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.accessory_for = '{sub_kat_lvl1}' 
                        AND category.superior_category = '{sub_kat_lvl2}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Bezeichnung', 'Seriennr.', 'Details', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

            results = [list(i) for i in results]

            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'

        stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.accessory_for = '{sub_kat_lvl1}' 
                    AND category.superior_category = '{sub_kat_lvl2}'
                    AND category.name = '{sub_kat_lvl3}'
                    {search_stmt}
                    {order_stmt} ;''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(
                f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

        results = [list(i) for i in results]
        return col_labels, results

    if cat == 'ersatzteile':

        if sub_kat_lvl2 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'

            stmt=(f'''SELECT repair.repair_id, repair.state, item.item_id, category.superior_category,
                                            category.name, item.name, item.serial_number, item.state, item.amount, item.price,
                                            warehouse.box_number
                                            FROM item INNER JOIN category
                                            ON item.id_category = category.category_id
                                            LEFT JOIN warehouse
                                            ON item.id_warehouse = warehouse.warehouse_id
                                            LEFT JOIN repair
                                            ON item.id_repair = repair.repair_id
                                            LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                                            WHERE item.internal = '1'  
                                            AND item.id_sale IS NULL 
                                            AND item.id_online_upload is NULL
                                            AND spare_part.spare_part_id IS NULL {filter_stmt}
                                            AND category.spare_part_for = '{sub_kat_lvl1}'
                                            {search_stmt}
                                            {order_stmt};''')
            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            results = [list(i) for i in results]

            return col_labels, results

        if sub_kat_lvl3 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'
            stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, 
                        category.name, item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.spare_part_for = '{sub_kat_lvl1}' 
                        AND category.superior_category = '{sub_kat_lvl2}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Katgeorie', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']
            results = [list(i) for i in results]
            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'
        stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.spare_part_for = '{sub_kat_lvl1}' 
                    AND category.superior_category = '{sub_kat_lvl2}'
                    AND category.name = '{sub_kat_lvl3}'
                    {search_stmt}
                    {order_stmt};''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

        results = [list(i) for i in results]

        return col_labels, results

    if cat == "anderes":
        if sub_kat_lvl1 == 'alle':
            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'
            stmt=(f'''SELECT repair.repair_id, repair.state, item.item_id, category.superior_category, category.name, 
                                            item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                                            FROM item INNER JOIN category
                                            ON item.id_category = category.category_id
                                            LEFT JOIN repair
                                            ON item.id_repair = repair.repair_id
                                            LEFT JOIN warehouse
                                            ON item.id_warehouse = warehouse.warehouse_id
                                            LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                                            WHERE item.internal = '1'  
                                            AND item.id_sale IS NULL 
                                            AND item.id_online_upload is NULL
                                            AND spare_part.spare_part_id IS NULL {filter_stmt}
                                            AND category.spare_part_for = '' 
                                            AND category.accessory_for = ''
                                            {search_stmt}
                                            {order_stmt};''')
            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

            try:
                results = db.session.execute(stmt).fetchall()

            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            results = [list(i) for i in results]

            return col_labels, results

        if sub_kat_lvl2 == 'alle':
            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'
            stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id,  category.name,
                        item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.spare_part_for = '' 
                        AND category.accessory_for = ''
                        AND category.superior_category = '{sub_kat_lvl1}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Kategorie', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

            results = [list(i) for i in results]

            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'
        stmt = (f'''SELECT repair.repair_id, repair.state, item.item_id, item.name, item.serial_number, item.state, item.amount, item.price, warehouse.box_number
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.spare_part_for = '' 
                    AND category.accessory_for = ''
                    AND category.superior_category = '{sub_kat_lvl1}'
                    AND category.name = '{sub_kat_lvl2}'
                    {search_stmt}
                    {order_stmt};''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in query_specific_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        col_labels = ['REPAIRID', 'REPAIRSTATE', 'ID', 'Bezeichnung', 'Seriennr.', 'Status', 'Anzahl', '(Einzel)-Preis', 'Kisten-ID']

        results = [list(i) for i in results]
        return col_labels, results


def query_specific_items_for_csv(cat, sub_kat_lvl1, sub_kat_lvl2, sub_kat_lvl3, filter_stmt, sort_value, name_search_val, sn_search_val):

    search_stmt = ''
    if name_search_val is not None and name_search_val != '':
        search_value = name_search_val.lower()
        search_stmt += f'''AND LOWER(item.name) LIKE '%{search_value}%' '''

    if sn_search_val is not None and sn_search_val != '':
        search_value = sn_search_val.lower()
        search_stmt += f'''AND LOWER(item.serial_number) LIKE '%{search_value}%' '''

    order_stmt = ''
    if sort_value == 'name':
        order_stmt = 1
    elif sort_value == 'id':
        order_stmt = '''ORDER BY item.item_id'''
    elif sort_value == 'add_date':
        order_stmt = 'ORDER BY UNIX_TIMESTAMP(item.check_date) desc'
    elif sort_value == 'edit_date':
        order_stmt = 'ORDER BY UNIX_TIMESTAMP(item.edit_date) desc'
    else:
        #box_no
        order_stmt = 'ORDER BY warehouse.box_number desc'

    col_labels = ['ID', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Seriennr.', 'Anzahl', 'Einzelpreis', 'Beschreibung', 'Status']

    #name date id box_no
    if cat == 'zubehoer':

        if sub_kat_lvl2 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'

            stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.accessory_for = '{sub_kat_lvl1}'
                        {search_stmt}
                        {order_stmt};''')
            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if sub_kat_lvl3 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'

            stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.accessory_for = '{sub_kat_lvl1}' 
                        AND category.superior_category = '{sub_kat_lvl2}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'

        stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.accessory_for = '{sub_kat_lvl1}' 
                    AND category.superior_category = '{sub_kat_lvl2}'
                    AND category.name = '{sub_kat_lvl3}'
                    {search_stmt}
                    {order_stmt} ;''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(
                f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        return col_labels, results

    if cat == 'ersatzteile':

        if sub_kat_lvl2 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'

            stmt=(f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                                            FROM item INNER JOIN category
                                            ON item.id_category = category.category_id
                                            LEFT JOIN warehouse
                                            ON item.id_warehouse = warehouse.warehouse_id
                                            LEFT JOIN repair
                                            ON item.id_repair = repair.repair_id
                                            LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                                            WHERE item.internal = '1'  
                                            AND item.id_sale IS NULL 
                                            AND item.id_online_upload is NULL
                                            AND spare_part.spare_part_id IS NULL {filter_stmt}
                                            AND category.spare_part_for = '{sub_kat_lvl1}'
                                            {search_stmt}
                                            {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if sub_kat_lvl3 == "alle":

            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'
            stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.spare_part_for = '{sub_kat_lvl1}' 
                        AND category.superior_category = '{sub_kat_lvl2}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'
        stmt = (f'''SELECT SELECT item.item_id, category.superior_category,
                    category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.spare_part_for = '{sub_kat_lvl1}' 
                    AND category.superior_category = '{sub_kat_lvl2}'
                    AND category.name = '{sub_kat_lvl3}'
                    {search_stmt}
                    {order_stmt};''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        return col_labels, results

    if cat == "anderes":
        if sub_kat_lvl1 == 'alle':
            if order_stmt == 1:
                order_stmt = 'ORDER BY category.superior_category, category.name, item.name, item.item_id'
            stmt=(f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                                            FROM item INNER JOIN category
                                            ON item.id_category = category.category_id
                                            LEFT JOIN repair
                                            ON item.id_repair = repair.repair_id
                                            LEFT JOIN warehouse
                                            ON item.id_warehouse = warehouse.warehouse_id
                                            LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                                            WHERE item.internal = '1'  
                                            AND item.id_sale IS NULL 
                                            AND item.id_online_upload is NULL
                                            AND spare_part.spare_part_id IS NULL {filter_stmt}
                                            AND category.spare_part_for = '' 
                                            AND category.accessory_for = ''
                                            {search_stmt}
                                            {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()

            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if sub_kat_lvl2 == 'alle':
            if order_stmt == 1:
                order_stmt = 'ORDER BY category.name, item.name, item.item_id'
            stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                        FROM item INNER JOIN category
                        ON item.id_category = category.category_id
                        LEFT JOIN warehouse
                        ON item.id_warehouse = warehouse.warehouse_id
                        LEFT JOIN repair
                        ON item.id_repair = repair.repair_id
                        LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                        WHERE item.internal = '1'  
                        AND item.id_sale IS NULL 
                        AND item.id_online_upload is NULL
                        AND spare_part.spare_part_id IS NULL {filter_stmt}
                        AND category.spare_part_for = '' 
                        AND category.accessory_for = ''
                        AND category.superior_category = '{sub_kat_lvl1}'
                        {search_stmt}
                        {order_stmt};''')

            try:
                results = db.session.execute(stmt).fetchall()
            except SQLAlchemyError as e:
                app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            return col_labels, results

        if order_stmt == 1:
            order_stmt = 'ORDER BY item.name, item.item_id'
        stmt = (f'''SELECT item.item_id, category.superior_category,
                        category.name, item.name, item.serial_number, item.amount, item.price, item.description, item.state
                    FROM item INNER JOIN category
                    ON item.id_category = category.category_id
                    LEFT JOIN warehouse
                    ON item.id_warehouse = warehouse.warehouse_id
                    LEFT JOIN repair
                    ON item.id_repair = repair.repair_id
                    LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                    WHERE item.internal = '1'  
                    AND item.id_sale IS NULL 
                    AND item.id_online_upload is NULL
                    AND spare_part.spare_part_id IS NULL {filter_stmt}
                    AND category.spare_part_for = '' 
                    AND category.accessory_for = ''
                    AND category.superior_category = '{sub_kat_lvl1}'
                    AND category.name = '{sub_kat_lvl2}'
                    {search_stmt}
                    {order_stmt};''')

        try:
            results = db.session.execute(stmt).fetchall()
        except SQLAlchemyError as e:
            app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Fehler in query_specific_items_for_csv (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        return col_labels, results


def create_filter_stmt(filter_state, filter_checked_by, filter_edited_by):
    filter_stmt = ''

    if not filter_state and not filter_checked_by and not filter_edited_by:
        return filter_stmt

    if filter_state:
        filter_stmt += f''' AND ( item.state = '{filter_state[0]}' '''
        for fs in filter_state[1:]:
            filter_stmt += f''' OR item.state = '{fs}' '''
        filter_stmt += ')'

    if filter_checked_by:
        filter_stmt += f''' AND (item.id_checked_by = '{filter_checked_by[0]}' '''
        for fcb in filter_checked_by[1:]:
            filter_stmt += f''' OR item.id_checked_by = '{fcb}' '''
        filter_stmt += ')'

    if filter_edited_by:
        filter_stmt += f''' AND (item.id_edited_by = '{filter_edited_by[0]}' '''
        for fcb in filter_edited_by[1:]:
            filter_stmt += f''' OR item.id_edited_by = '{fcb}' '''
        filter_stmt += ')'

    return filter_stmt


def remove_items_in_reverse_cart(t_content):
    reverse_cart_ids = session.get('reverse_cart')
    if reverse_cart_ids == '' or reverse_cart_ids is None:
        return t_content
    for elem in list(t_content):
        if str(elem[2]) in reverse_cart_ids:
            t_content.remove(elem)

    return t_content


#for sort_ajax and search_ajax
#builds html string, that will send back as ajax response
def build_content_html(t_header, t_content):

    t_content = remove_items_in_reverse_cart(t_content)

    html_str = f'''<div class="row mt-5 ">
                    <div class="col h5">Ergebnisse: {len(t_content)}</div>
                   </div> '''
    html_str += '''<div class="row mt-5 ">
                    <div class="col-lg-1"> <div class="col form-check form-switch"> 
                             <input class="form-check-input border border-secondary fs-5" type="checkbox" onchange="select_all_change();" id="select_all" style="display:none;">
                    </div></div> '''

    for i in t_header[2:]:
        html_str += f'<div class="d-none d-lg-inline col-sm-auto col-lg-1 h6">{i}</div>'

    html_str += '''<div class="d-none d-lg-inline col-lg-1"></div>
                </div>''' #eo row

    #if t_content is not None:
    for row in t_content:

        #show color based on repair state
        color = "bg-light"
        color_css="#f8f9fa"
        if row[0]:
            color = "bg-warning"
            color_css="#ffc107"
            if row[1] == 'abgeschlossen':
                color = "bg-success"
                color_css="#198754"

        html_str += f'''<div class="row mb-5">
    
                        <div class="col-sm-auto col-lg-1">'''
        if not row[0]:
            html_str += f'''<input class="form-check-input mt-2 border border-secondary fs-5" type="checkbox" value="{row[2]}" style="display:none;">'''

        html_str += '''</div> '''

        for idx, cell in enumerate(row[2:]):

            if cell is None:
                cell=''

            #amount cell:
            if idx==len(row[2:])-3:
                html_str+= f'<div class="d-flex col-sm-auto  col-lg-1 border border-secondary {color}"><input id="item_amount{row[2]}" style="width:80%;height:50px;margin:auto;border:none;background-color:{color_css};" type="number" min="1" oninput="ajax_change_item_amount({row[2]});" onchange="ajax_change_item_amount({row[2]});" value="{cell}">  </div>'

            #price cell:
            elif idx==len(row[2:])-2:
                if cell!=0:
                    html_str += f'<div class="col-sm-auto text-wrap text-break col-lg-1 border border-secondary {color}"><span id="single_price{row[2]}">{str(cell)[:-2]},{str(cell)[-2:]} €</span>'

                    #create price sum if amount > 1:
                    if row[len(row)-3]!=1:
                        price_sum=cell*row[len(row)-3]
                        html_str+=f'<br><span class="mt-2" id="total_price{row[2]}"> ({str(price_sum)[:-2]},{str(price_sum)[-2:]} €)</span>'
                        print(row[len(row)-3])
                    html_str+='</div>'
                else:
                    html_str += f'<div class="col-sm-auto text-wrap text-break col-lg-1 border border-secondary {color}">0,00 €</div> '
            #everything else:
            else:
                html_str += f'<div class="d-flex col-sm-auto text-wrap text-center text-break col-lg-1 border border-secondary {color}">{cell}</div> '

            #if idx != (len(row[2:])-2) and idx != len(row[2:])-3 and idx != len(row[2:])-4 and idx != len(row[2:])-5:
            #    if cell is None:
            #        cell = '-'
            #    html_str += f'<div class="col-sm-auto text-wrap text-break col-lg-1 border border-secondary {color}">{cell}</div> '
            #elif idx == (len(row[2:])-3) or idx == (len(row[2:])-5):
            #    if cell is None:
            #        html_str += f'<div class="col-sm-auto text-wrap text-break col-lg-1 border border-secondary {color}">-</div> '
            #    else:
            #        html_str += f'<div class="col-sm-auto text-wrap text-break col-lg-1 border border-secondary {color}">{cell}:{row[2+idx+1]}</div> '
#
        #html_str += '''</div>'''  #eo row

        #<div class="row mt-2 mb-5">
        #<div class="col-lg-4 d-flex justify-content-start align-items-baseline">

        html_str += f'''
                            <div class="col-lg-1">
                            
                            
                                <form action="{ url_for('inventory_bp.product_details', idd=row[2]) }"> 
                                    <button type="submit" class="btn btn-primary me-2" value="details" onclick="save_scroll_pos();save_kats();"> Details </button>
                                </form>
                            </div>    
                         '''

        if not(row[0] and row[1] != 'abgeschlossen'):
            html_str += f'''<div class="col-lg-1"> 
                                <span data-bs-toggle="modal" data-bs-target="#sell_single_item{row[2]}" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Item einzeln verkaufen.">
                                    <button type="button" class="btn btn-success float-end me-2" value="{row[2]}" >
                                       <i class="feather-16" data-feather="shopping-bag"></i>
                                    </button>
                                </span>
                            '''
            if current_user.admin_role == 1:
                html_str += f'''
                                <button type="button" onclick="open_upload_item(this.value);" class="btn btn-success me-2" value="{row[2]}">
                                          <i class="feather-16" data-feather="upload"></i>
                                </button> </div>'''

        html_str += '''     </div>'''
        
        #html_str += '''      <div class="col-lg-7"></div>'''
        html_str +='''</div>''' #eo row

        html_str += f'''<div class="modal fade" id="sell_single_item{row[2]}" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-labelledby="staticBackdropLabel" aria-hidden="true">
                              <div class="modal-dialog">
                                <div class="modal-content">
                                  <div class="modal-header">
                                    <h5 class="modal-title">Verkauf abschließen</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                  </div>
                                    <form method="POST">
                                  <div class="modal-body">

							          <div class="row mt-3">
							               <div class="col-lg-1 col-md-1"></div>
							               <div class="col-lg-5 col-md-5 h6">Preis (€): </div>
							               <div class="col-lg-5 col-md-5">
                                               <input class="form-control" name="price" type="text" pattern="[0-9]{'{1,4}'},[0-9]{'{2}'}" placeholder="10,00" required>
                                           </div>
							               <div class="col-lg-1 col-md-1"></div>
							          </div>

                                      <div class="row mt-3">
							               <div class="col-lg-1 col-md-1"></div>
							               <div class="col-lg-5 col-md-5 h6">Kommentar</div>
							               <div class="col-lg-5 col-md-5">
							                <textarea class="form-control border border-dark" name="description" rows="3"></textarea>
							               </div>
							               <div class="col-lg-1 col-md-1"></div>
							          </div>
							                   
                                         <input type="hidden" name="item_id" value="{row[2]}" >
                                  </div>
                                  <div class="modal-footer justify-content-center">
                                    <button type="submit" name="sell_single_item" onclick="save_scroll_pos();save_kats();" class="btn btn-primary">Verkauf abschließen</button>
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>
                                  </div>
                                  </form>
                                </div>
                              </div>
                            </div>'''

    #endif
    html_str += '</div>'

    return html_str


def query_all_items(filter_stmt, in_repair):

    if in_repair:
        rep = 'NOT'
    else:
        rep = ''

    stmt = (f'''SELECT GROUP_CONCAT(item.item_id), category.spare_part_for, category.superior_category,
                category.name, item.name, item.state, count(*)
                FROM item
                LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                INNER JOIN category ON item.id_category = category.category_id
                WHERE category.spare_part_for != '' AND item.internal = '1'  
                AND category.spare_part_for IS NOT NULL AND spare_part.spare_part_id IS NULL
                AND item.id_sale IS NULL AND item.id_repair IS {rep} NULL {filter_stmt}
                AND item.id_online_upload is NULL
                GROUP BY category.category_id, item.name, item.description, item.state
                ORDER BY category.spare_part_for, category.superior_category,
                category.name, item.name, item.description, item.state ;''')

    try:
        et_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in query_all_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    et_header = ['Ersatzteil Von', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Status', 'Anzahl']

    stmt = (f'''SELECT GROUP_CONCAT(item.item_id), category.accessory_for, category.superior_category,
                category.name, item.name, item.state, count(*)
                FROM item
                LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                INNER JOIN category ON item.id_category = category.category_id
                WHERE category.accessory_for != '' AND item.internal = '1'  
                AND spare_part.spare_part_id IS NULL
                AND item.id_sale IS NULL AND item.id_repair IS {rep} NULL {filter_stmt}
                AND category.accessory_for IS NOT NULL
                AND item.id_online_upload is NULL
                GROUP BY category.category_id, item.name, item.description, item.state
                ORDER BY category.accessory_for, category.superior_category,
                category.name, item.name, item.state;''')

    try:
        zb_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in query_all_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    zb_header = ['Zubehör Von', 'Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Status', 'Anzahl']

    stmt = (f'''SELECT GROUP_CONCAT(item.item_id), category.superior_category,
                category.name, item.name, item.state, count(*)
                FROM item
                INNER JOIN category ON item.id_category = category.category_id
                LEFT JOIN spare_part ON item.item_id = spare_part.id_item
                WHERE item.internal = '1'  
                AND item.id_sale IS NULL 
                AND item.id_online_upload is NULL
                AND spare_part.spare_part_id IS NULL AND item.id_repair IS {rep} NULL {filter_stmt}
                AND category.spare_part_for=''
                AND category.accessory_for=''
                GROUP BY category.category_id, item.name, item.description, item.state
                ORDER BY category.superior_category, category.name,
                item.name, item.state; ''')

    try:
        sonst_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        app.logger.error(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in query_all_items (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    sonst_header = ['Top-Kategorie', 'Kategorie', 'Bezeichnung', 'Status', 'Anzahl']

    return et_content, et_header, zb_content, zb_header, sonst_content, sonst_header

#INPUT VALUES-----------------------------------------------------------------------------------------------------------

#checks whether user wants to add a new category name (+ returns error in case that value is empty)
#case new category -> addds category entry to database + returns cat_id
#case existing category -> seacrhes for category entry in database + returns cat_id

def handle_category_input():

    #Geräte --------------------------------------------------------------------------------------------------------
    if request.form.get('kategorie') == 'anderes':

        #is value for sub_kat selected or user input:
        if request.form.get('a_sub_kat') == 'neu':
            a_sub_kat = request.form.get('a_sub_kat_input')

            #category without "name" can not be inserted
            if a_sub_kat == '':
                    return "empty"
        else:
            a_sub_kat = request.form.get('a_sub_kat')

        try:
            #returns None if entry doesnt exist yet
            cat_id = get_cat_id(request.form.get('anderes_top_kat'), a_sub_kat, '', '')
        except Exception as e:
            raise Exception(str(e))

        #hopefully only in case category "name" is "neu" -> a_sub_cat_input
        # i mean if its set by selection the category should exists
        if cat_id is None:
            k = category_table(name=request.form.get('a_sub_kat_input'),
                               superior_category=request.form.get('anderes_top_kat'),
                               accessory_for='', spare_part_for='')

            try:
                db.session.add(k)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy ADD exception in handle_category_input. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in handle_category_input (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}')

            cat_id = k

        return cat_id

    #Ersatzteile++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if request.form.get('kategorie') == 'ersatzteile':

        #is value for sub_kat selected or user input:
        if request.form.get('ersatzteile_sub_kat') == 'neu':

            et_sub_kat = request.form.get('et_sub_kat_input')

            #category without "name" can not be inserted
            if et_sub_kat == '':
                    return "empty"
        else:
            et_sub_kat = request.form.get('ersatzteile_sub_kat')

        try:
            #returns None if entry doesnt exist yet
            cat_id = get_cat_id(request.form.get('ersatzteile_top_kat'),
                                et_sub_kat, '', request.form.get('ersatzteile_et'))
        except Exception as e:
            raise Exception(str(e))

        if cat_id is None:
            k = category_table(name=request.form.get('et_sub_kat_input'),
                               superior_category=request.form.get('ersatzteile_top_kat'),
                               accessory_for='', spare_part_for=request.form.get('ersatzteile_et'))

            try:
                db.session.add(k)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy ADD exception in handle_category_input. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in handle_category_input (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}')

            cat_id = k

        return cat_id

    #Zubehör+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if request.form.get('kategorie') == 'zubehoer':

        #is value for sub_kat selected or user input:
        if request.form.get('zubehoer_sub_kat') == 'neu':

            zb_sub_kat = request.form.get('zb_sub_kat_input')
            if zb_sub_kat == '':
                    return "empty"
        else:
            zb_sub_kat = request.form.get('zubehoer_sub_kat')

        try:
            #returns None if entry doesnt exist yet
            cat_id = get_cat_id(request.form.get('zubehoer_top_kat'),
                             zb_sub_kat, request.form.get('zubehoer_zb'), '')
        except Exception as e:
            raise Exception(str(e))

        if cat_id is None:
            k = category_table(name=request.form.get('zb_sub_kat_input'),
                               superior_category=request.form.get('zubehoer_top_kat'),
                               accessory_for=request.form.get('zubehoer_zb'), spare_part_for='')

            try:
                db.session.add(k)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy ADD exception in handle_category_input. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Fehler in handle_category_input (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}')

            cat_id = k

        return cat_id



#for product details:+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def get_item_details(idd):
    try:
        cat = db.session.query(category_table.name, category_table.category_id,
                                category_table.spare_part_for, category_table.accessory_for)\
                                .join(item_table).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")


    #ersatzteile:
    if cat.spare_part_for is not None and cat.spare_part_for != '':
        try:
            results = db.session.query(item_table.name.label('item_name'), item_table.item_id, category_table.superior_category,
                                       category_table.name.label('category_name'), item_table.serial_number, item_table.amount,
                                       item_table.price, category_table.spare_part_for, item_table.description
                                      ).join(category_table).filter(
                                        item_table.item_id == idd).first()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("SQLAlchemy Query Error.")

        prod_details = {
            "Ersatzteil von": results.spare_part_for,
            "Kategorie-ID": cat.category_id,
            "Top-Kategorie": results.superior_category,
            "Kategorie": results.category_name,
            "ID": results.item_id,
            "Bezeichnung": results.item_name,
            "Seriennummer": results.serial_number,
            "Beschreibung": results.description,
            "Preis": results.price,
            "Anzahl": results.amount
        }
    #zubehoer
    elif cat.accessory_for is not None and cat.accessory_for != '':

        try:
            results = db.session.query(item_table.name.label('item_name'), item_table.item_id, category_table.superior_category,
                                   category_table.name.label('category_name'), item_table.serial_number, item_table.price, item_table.amount,
                                   category_table.accessory_for, item_table.description
                                   ).join(category_table).filter(
                                    item_table.item_id == idd).first()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("SQLAlchemy Query Error.")

        prod_details = {
            "Zubehör von": results.accessory_for,
            "Kategorie-ID": cat.category_id,
            "Top-Katgeorie": results.superior_category,
            "Kategorie": results.category_name,
            "ID": results.item_id,
            "Bezeichnung": results.item_name,
            "Seriennummer": results.serial_number,
            "Beschreibung": results.description,
            "Preis": results.price,
            "Anzahl": results.amount
        }
    #Geräte
    else:
        try:
            results = db.session.query(item_table.name.label('item_name'), item_table.item_id, category_table.superior_category,
                                   category_table.name.label('category_name'), item_table.description, item_table.serial_number,
                                   item_table.price, item_table.amount,
                                   ).join(category_table).filter(
                                    item_table.item_id == idd).first()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("SQLAlchemy Query Error.")

        prod_details = {
            "Kategorie-ID": cat.category_id,
            "Top-Kategorie": results.superior_category,
            "Kategorie": results.category_name,
            "ID": results.item_id,
            "Bezeichnung": results.item_name,
            "Seriennummer": results.serial_number,
            "Beschreibung": results.description,
            "Preis": results.price,
            "Anzahl": results.amount
        }

    try:
        results = db.session.query(item_table.state, item_table.id_checked_by, item_table.id_edited_by,
                                   item_table.check_date, item_table.edit_date).filter(
                                    item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    edit_date = results.edit_date
    if edit_date:
        edit_date = format_datetime(edit_date, locale='de_DE')
    pruefung = {
        "Status": results.state,
        "Hinzugefügt von": User.query.filter(results.id_checked_by == User.user_id).first().username,
        "Hinzugefügt am": format_datetime(results.check_date, locale='de_DE'),
        "edited_by": User.query.filter(results.id_edited_by == User.user_id).first(),
        "Zuletzt Geupdated am": edit_date
    }

    item_details = prod_details
    item_details.update(pruefung)

    return item_details


def get_item_warehouse_details(idd):

    lager = None

    try:
        results = db.session.query(warehouse_table.shelf_number, warehouse_table.compart_number, warehouse_table.box_number,
                                    warehouse_table.description).join(item_table).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if results is not None:
        lager = {
            "Schrank-ID": results.shelf_number,
            "Fach-ID": results.compart_number,
            "Kisten-ID": results.box_number,
            "Beschreibung": results.description
        }

    return lager


def get_item_repair_info(idd):

    repair_info = None
    try:
        repair_results = db.session.query(repair_table.state, repair_table.repair_id).join(item_table).filter(
                                    item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(
            f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if repair_results:

        repair_info = {
            "ID": repair_results.repair_id,
            "state": repair_results.state,
        }

    return repair_info


#wird das Item als Ersatzteil verwendet oder ist es bereits verkauft, oder ist es Teil eines Auftrages (dann ist es nicht verfügbar)
def get_item_availability(idd):

    available = True

    #verkauft?:
    try:
        is_sold = db.session.query(item_table.id_sale).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if is_sold.id_sale:
        try:
            sale_results = db.session.query(sale_table).filter(sale_table.sale_id == is_sold.id_sale).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("SQLAlchemy Query Error.")

        availability = {
            "available": False,
            "reason_id": "sold",
            "reason": "verkauft",
            "date": format_datetime(sale_results.date, locale='de_DE'),
            "ID": sale_results.sale_id
        }

        return availability

    #online?!
    try:
        is_online = db.session.query(item_table.id_online_upload).filter(item_table.item_id == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if is_online.id_online_upload:

        availability = {
            "available": False,
            "reason_id": "online",
            "reason": "online gestellt",
            "ID": is_online.id_online_upload
        }

        return availability

    #extern bzw Teil eines Auftrages?
    try:
        is_external = db.session.query(repair_order_table).filter(repair_order_table.id_item == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if is_external:
        try:
            repair_order_results = db.session.query(repair_order_table.issue_date, repair_order_table.repair_order_id, customer_table.name).join(customer_table).filter(repair_order_table.id_item == idd).first()
        except SQLAlchemyError as e:
            app.logger.warning(
                f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("SQLAlchemy Query Error.")

        availability = {
            "available": False,
            "reason_id": "order",
            "reason": "Teil eines Auftrages",
            "customer": repair_order_results.name,
            "date": format_datetime(repair_order_results.issue_date, locale='de_DE'),
            "ID": repair_order_results.repair_order_id
        }
        return availability

    #Ersatzteil in einer Reparatur?:
    try:
        is_spare_part = db.session.query(spare_part_table).filter(spare_part_table.id_item == idd).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path} (get_item_warehouse_details). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("SQLAlchemy Query Error.")

    if is_spare_part:
        availability = {
            "available": False,
            "reason_id": "spare_part",
            "reason": "Ersatzteil in einer Reparatur",
            "ID": is_spare_part.id_repair
        }
        return availability

    availability = {
        "available": available
    }

    return availability