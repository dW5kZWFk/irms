from flask_mail import Message
from flask import request
from flask_login import current_user
from application import db, mail, app
from application.models import repair_table, repair_order_table, spare_part_table, item_table, service_table, category_table, User
from sqlalchemy import update
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import os
from babel.dates import format_datetime


#for spare_parts not bound to items yet
#availability for deleting, or editing spare part
#not available if it is already deleted, or has state "vorhanden"
def check_spare_part_not_available(sp_id):

    try:
        sp_results = db.session.query(spare_part_table.spare_part_id, spare_part_table.id_item).filter(spare_part_table.spare_part_id == sp_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Prüfen der Ersatzteil Verfügbarkeit fehlgeschlagen. {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if sp_results is None or sp_results.id_item is not None:
        return True
    return False


def check_repair_order_not_available(o_id):

    try:
        rp_results = db.session.query(repair_order_table.repair_order_id, repair_order_table.state).filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Prüfen der Auftrags Verfügbarkeit fehlgeschlagen. {e} (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if rp_results is None or rp_results.state == "abgeschlossen":
        return True
    return False


#wenn ersatzteile mit dem Status "benötigt / bestellt" existieren, sollte der reparatur status angepasst werden (et benötigt / et bestellt)
#funktion wird aufgerufen, bevor Reparatur Details angezeigt werden !
def check_repair_state(r_id):

    try:
        r_state = db.session.query(repair_table.state).filter(repair_table.repair_id == r_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}'")

    #existieren Ersatzteile im state "benötigt"?:
    try:
        et_state_needed = db.session.query(spare_part_table).filter(spare_part_table.id_repair == r_id, spare_part_table.state=='benötigt').first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}'")
    if et_state_needed is not None:
        if r_state.state == "benötigt":
            return None
        else:
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(state="Ersatzteile benötigt", edit_date=datetime.now(), id_edited_by=1)

            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}'")
            return None


    #falls nicht: existieren Ersatzteile im state "bestellt"?
    try:
        et_state_ordered = db.session.query(spare_part_table).filter(spare_part_table.id_repair == r_id, spare_part_table.state == 'bestellt').first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}'")

    if et_state_ordered is not None:
        if r_state.state == "benötigt":
            return None
        else:
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(state="Ersatzteile bestellt", edit_date=datetime.now(), id_edited_by=1)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}'")
            return None

    #wurden alle Ersatzteile gelöscht? -> setze Status auf "laufend"
    try:
        et_results = db.session.query(spare_part_table).filter(spare_part_table.id_repair == r_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}'")

    if et_results is None:
        if r_state.state == "laufend" or r_state.state == "abgeschlossen" or r_state.state == "neu":
            return None
        else:
            stmt = update(repair_table).where(repair_table.repair_id == r_id).values(state="laufend",
                                                                                     edit_date=datetime.now(),
                                                                                     id_edited_by=1)
            try:
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(
                    f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(
                    "f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}'")
            return None

    #falls nicht: existieren Ersatzteile, aber der state ist nicht "laufend" / "abgeschlossen" ?
    #(! wichtig um Reparatur aus dem Status "Ersatzteile bestellt" rauszuholen !)
    try:
        et_state_third_case =  db.session.query(spare_part_table).filter(spare_part_table.id_repair == r_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}'")
    if et_state_third_case is not None and r_state.state != "abgeschlossen" and r_state.state != "laufend":
        stmt = update(repair_table).where(repair_table.repair_id == r_id).values(state="laufend", edit_date=datetime.now(), id_edited_by=1)
        try:
            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception("f' Raparatur Status konnte nicht automatisch angepasst werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}'")
        return None

    return None


def check_order_state(o_id):

    now = datetime.now()
    #Reparatur Eintrag vorhanden
        #Status != "neu" ? -> setze Status auf "laufend"
        #Status == "abgeschlossen" -> Setze Status auf "warten auf Abholung"

    #kein Reapratur Eintrag vorhanden
        #status variabel veränderbar

    try:
        existing_repair = db.session.query(repair_table).join(repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Update des Auftrags-Status gescheitert (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    if existing_repair is None:
        return None

    try:
        r_state_o_state_o_id = db.session.query(repair_table.state.label("r_state"), repair_order_table.state.label("o_state"),
                                                repair_order_table.repair_order_id, repair_order_table.id_sale).join(repair_order_table)\
                                                .filter(repair_order_table.repair_order_id == o_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Update des Auftrags-Status gescheitert (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')


    #no repair entry
    if r_state_o_state_o_id is None:
        return None

    if r_state_o_state_o_id.id_sale is not None:
        return None

    #Status == "abgeschlossen" -> Setze Status auf "warten auf Abholung"
    if r_state_o_state_o_id.o_state != "warten auf Abholung" and r_state_o_state_o_id.r_state == "abgeschlossen":
        stmt = (
            update(repair_order_table).where(
                repair_order_table.repair_order_id == o_id).values(state="warten auf Abholung", edit_date=now, id_edited_by=1)
        )
        try:
            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Update des Auftrags-Status gescheitert (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}')

        return None

    #Status != "neu" ? -> setze Status auf "laufend"
    if r_state_o_state_o_id.o_state != 'laufend' and r_state_o_state_o_id.r_state != "neu" and r_state_o_state_o_id.r_state != "abgeschlossen":
        stmt = (
            update(repair_order_table).where(
                repair_order_table.repair_order_id == o_id).values(
                state="laufend", edit_date=now, id_edited_by=1)
        )

        try:
            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Update des Auftrags-Status gescheitert (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}')

        return None

    #Status != "abgeschlossen" und Auftrag Status == "warten auf abholung"? Setze Status auf "laufend"
    if r_state_o_state_o_id.o_state == "warten auf Abholung" and r_state_o_state_o_id.r_state != "abgeschlossen":
        stmt = (
            update(repair_order_table).where(
                repair_order_table.repair_order_id == o_id).values(
                state="laufend", edit_date=now, id_edited_by=1)
        )

        try:
            db.session.execute(stmt)
            db.session.commit()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Update des Auftrags-Status gescheitert (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}')

        return None

    return None


def delete_spare_part(sp_id):
    try:
        r_id = db.session.query(spare_part_table.id_repair).filter(spare_part_table.spare_part_id == sp_id).first().id_repair
        db.session.query(spare_part_table).filter(spare_part_table.spare_part_id == sp_id).delete()
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.warning(f'SQLAlchemy Query/DELETE exception on {request.path} (delete_spare_part). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Ersatzteil konnte nicht gelöscht werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}')

    try:
        update_repair_edit(r_id, current_user.user_id)
    except Exception as e:
        raise Exception(str(e))
    return None


def update_repair_edit(r_id, u_id):
    stmt = update(repair_table).where(repair_table.repair_id == r_id).values(edit_date=datetime.now(), id_edited_by=u_id)
    try:
        db.session.execute(stmt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f'SQLAlchemy UPDATE exception on {request.path} (update_repair_edit). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Letzter Bearbeiter des Reparatur Eintrages konnte nicht angepasst werden. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}')
    return None


#add and change item.id_repair
def add_repair(i_id):

    #add new repair entry
    r = repair_table(state='neu', description=request.form.get("repair_description"), id_edited_by=current_user.user_id)

    try:
        db.session.add(r)
        db.session.flush()
        r_id = r.repair_id

        #link repair entry with item
        i = db.session.query(item_table).filter(item_table.item_id == i_id).first()

        i.id_repair = r.repair_id
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.warning(f'SQLAlchemy ADD/Update exception on {request.path} (add_repair). Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f" Reparatur Eintrag konnte nicht hinzugefügt oder mit dem Item in Zusammenhang gesetzt werden. Manuelle Prüfung notwendig. (SQLAlchemy add/update() error) -> Logfile Eintrag: {datetime.now()}'")

    return r_id


#für "abgeschlossen" (1) und nicht abgeschlossen (0)
def get_repair_orders_dict_list(o_id, name, order_state, per_page, offset):

    repair_order_ids = [o_id]
    orders_total = 0

    #1 get all order_ids
    if order_state == 1 and o_id is None:

        #get finished order by name
        if name is not None:
            try:
                name = name.lower()
                name = name.replace(" ", "")

                repair_order_ids = [r.repair_order_id for r in db.session.execute(f'''SELECT repair_order_id FROM repair_order INNER JOIN
                                                                                      customer on repair_order.id_customer = customer.customer_id
                                                                                      WHERE state = 'abgeschlossen'
                                                                                      AND LOWER(REPLACE(customer.name, ' ', '')) LIKE '%{name}%' 
                                                                                      ORDER BY UNIX_TIMESTAMP(edit_date) desc ''')]
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            if len(repair_order_ids) == 0:
                return 0, 0

        #get all finished orders
        else:
            try:
                repair_order_ids = [r.repair_order_id for r in db.session.execute(f'''SELECT repair_order_id FROM repair_order WHERE
                                                                                      state = 'abgeschlossen' ORDER BY UNIX_TIMESTAMP(edit_date)  
                                                                                      desc LIMIT {per_page} OFFSET {offset}''')]
                orders_total = len(db.session.query(repair_order_table.repair_order_id).filter(repair_order_table.state == 'abgeschlossen').all())
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    elif o_id is None:
        #get open orders by name
        if name is not None:
            try:
                name = name.lower()
                name = name.replace(" ", "")
                repair_order_ids = [r.repair_order_id for r in db.session.execute(f'''SELECT repair_order_id FROM repair_order INNER JOIN
                                                                                                  customer on repair_order.id_customer = customer.customer_id
                                                                                                  WHERE state != 'abgeschlossen' 
                                                                                                  AND LOWER(REPLACE(customer.name, ' ', '')) LIKE '%{name}%' 
                                                                                                  ORDER BY repair_order_id desc ''')]
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            if len(repair_order_ids) == 0:
                return 0, 0

        else:
            #get all open orders
            try:
                repair_order_ids = [r.repair_order_id for r in db.session.execute(f'''SELECT repair_order_id FROM repair_order WHERE
                                                                                      state != 'abgeschlossen' ORDER BY repair_order_id 
                                                                                      desc LIMIT {per_page} OFFSET {offset}''')]
                orders_total = len(db.session.query(repair_order_table.repair_order_id).filter(
                    repair_order_table.state != 'abgeschlossen').all())
            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    #all repair entries without items
    #repair_ids.extend( [r.repair_id for r in db.session.query(repair_table.repair_id).join(item_table, isouter=True).filter(item_table.id_repair == None )] )

    #select repair.repair_id from repair LEFT JOIN item on item.id_repair = repair.repair_id WHERE id_repair IS NULL;
    #toDo: wird das Item zu einem reparatur Eintrag gelöscht, dann entstehen verwaiste Reparatur Einträge -> sollte nicht mehr löschbar sein (Löschung des Lösch-Buttons!)
    #abgeschlossen

    dict_list = []

    for o_id in repair_order_ids:
        try:
            #state of order gets changed in dependence of repair state
            check_order_state(o_id)
        except Exception as e:
            raise Exception(str(e))

        try:
            results_order = db.session.query(repair_order_table.state, repair_order_table.issue_date,repair_order_table.description,
                                             repair_order_table.delivery_date, repair_order_table.id_edited_by,
                                             repair_order_table.edit_date, repair_order_table.id_item, repair_order_table.id_sale)\
                                        .filter(repair_order_table.repair_order_id == o_id).first()
            edit_user = User.query.filter(User.user_id == results_order.id_edited_by).first()
            result_repair = db.session.query(repair_table.state, repair_table.repair_id, repair_table.price).filter(
                repair_table.id_repair_order == o_id).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        repair_state = '-'
        repair_id = '-'
        r_price = '-'
        if result_repair is not None:
            repair_state = result_repair.state
            repair_id = result_repair.repair_id
            if result_repair.price is not None:
                r_price = str(result_repair.price).replace('.', ',')

        device_name = '-'
        if results_order is not None:

            if results_order.id_item:
                stmt = (f'''SELECT item.name as "i_name", category.superior_category, category.accessory_for, 
                            category.spare_part_for, category.name,
                            category.category_id
                            FROM category INNER JOIN item ON category.category_id = item.id_category
                            WHERE item.item_id ={results_order.id_item};''')
                try:
                    results_category = db.session.execute(stmt).first()
                    db.session.commit()
                except SQLAlchemyError as e:
                    app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

                device_name = str(results_category.name) + ' ' + str(results_category.i_name)

            stmt = (f'''SELECT customer.customer_id, customer.name FROM customer INNER JOIN repair_order 
                        ON repair_order.id_customer = customer.customer_id
                        WHERE repair_order.repair_order_id = {o_id};''')

            try:
                results_customer = db.session.execute(stmt).first()
                db.session.commit()

                result_service = db.session.query(service_table.service_id, service_table.name).join(
                    repair_order_table).filter(repair_order_table.repair_order_id == o_id).first()

            except SQLAlchemyError as e:
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                raise Exception(f' Laden vorhandener Aufträge gescheitert. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

            service_id = '-'
            service_name = '-'

            if result_service is not None:
                service_id = result_service.service_id
                service_name = result_service.name

            o_date = results_order.issue_date
            if order_state == 1:
                status_sale_id = results_order.id_sale
            else:
                status_sale_id = results_order.state

            description = results_order.description

            if description:
                if len(description) > 45:
                    description = description[0:46] + '(...)'

            if order_state == 0:
                last_date = f"{edit_user.username}:{format_datetime(results_order.edit_date, locale='de_DE')}"
            else:
                last_date = f"{edit_user.username}:{format_datetime(results_order.delivery_date, locale='de_DE')}"

            p = {
                "AuftragID": o_id,
                "status_sale_id": status_sale_id,
                "AuftragDatum": format_datetime(o_date, locale='de_DE'),
                "Kunde": results_customer.name,
                "zuletzt_bearbeitet": last_date,
                "KundeID": results_customer.customer_id,
                "Beschreibung": description,
                "ItemID": results_order.id_item,
                "Gerät": device_name,
                "ServiceID": service_id,
                "ServiceName": service_name,
                "ReparaturID": repair_id,
                "ReparaturStatus": repair_state,
                "ReparaturPreis": r_price,
                "full_description": results_order.description
            }
            dict_list.append(p)

    return dict_list, orders_total


def send_mail_to_customer(customer_name):

    file_path = os.path.join(app.root_path, 'static/mail_content.txt')

    try:
        with open(file_path, 'r') as f:
            email_content = f.read()
    except OSError as e:
        app.logger.warning(f"Failed to read E-Mail from OS.  Time: {datetime.now()}. Exception: {e}")
        raise Exception(f"Fehler beim Lesen der E-Mail Datei. -> Logfile Eintrag: {datetime.now()}")

    email_content_new = email_content.replace('{kundenname}', customer_name)

    msg = Message('', recipients=['an-dembowski@t-online.de'])
    msg.body = email_content_new

    try:
        mail.send(msg)
    except Exception as e:
        app.logger.warning(f"Failed to send E-Mail in send_mail_customer. Time: {datetime.now()}. Exception: {e}")
        raise Exception(f"E-Mail konnte nicht gesendet werden. -> Logfile Eintrag: {datetime.now()} ")

    return "Message sent!"


def get_internal_repair_dict(finished, per_page, offset):

    #1 => finished, 0 => open
    if finished == 1:
        stmt = f''' SELECT repair_id FROM repair INNER JOIN item ON item.id_repair = repair.repair_id
                  WHERE repair.id_repair_order IS NULL AND item.internal = 1 AND repair.state = "abgeschlossen" and
                  item.id_sale IS NULL ORDER BY repair.repair_id desc LIMIT {per_page} OFFSET {offset} '''
        stmt_2 = ''' SELECT repair_id FROM repair INNER JOIN item ON item.id_repair = repair.repair_id
                  WHERE repair.id_repair_order IS NULL AND item.internal = 1 AND repair.state = "abgeschlossen" and
                  item.id_sale IS NULL'''
    else:
        stmt = f''' SELECT repair_id FROM repair INNER JOIN item ON item.id_repair = repair.repair_id
                  WHERE repair.id_repair_order IS NULL AND item.internal = 1 AND repair.state != "abgeschlossen" and
                  item.id_sale IS NULL ORDER BY repair.repair_id desc LIMIT {per_page} OFFSET {offset} '''
        stmt_2 = ''' SELECT repair_id FROM repair INNER JOIN item ON item.id_repair = repair.repair_id
                  WHERE repair.id_repair_order IS NULL AND item.internal = 1 AND repair.state != "abgeschlossen" and
                  item.id_sale IS NULL'''

    try:
        repair_ids = [r.repair_id for r in db.session.execute(stmt)]
        repairs_total = len(db.session.execute(stmt_2).fetchall())
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Interne Reparaturen konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    internal_repairs = []
    for r_id in repair_ids:
        try:
            repair_results = db.session.query(repair_table).filter(repair_table.repair_id == r_id).first()
            item_results = db.session.query(item_table.item_id, item_table.name.label('i_name'),
                                        category_table.superior_category, category_table.name.label('c_name'))\
                                        .join(category_table).filter(item_table.id_repair == r_id).first()
            edit_username = User.query.filter(User.user_id == repair_results.id_edited_by).first()

        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Interne Reparaturen konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        r_dict = {
            "ReparaturID": r_id,
            "edit_date": format_datetime(repair_results.edit_date, locale='de_DE'),
            "edited_by": edit_username.username,
            "ID": item_results.item_id,
            "Gerät": f"{item_results.i_name} ({item_results.superior_category}, {item_results.c_name})",
            "Status": repair_results.state
        }

        internal_repairs.append(r_dict)

    return internal_repairs, repairs_total