import json
import os

import flask_login
import sqlalchemy
from flask import render_template, Blueprint, flash, request, url_for
from flask_login import login_required
from werkzeug.utils import redirect

from application import db, app
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError


home_bp = Blueprint('home_bp', __name__,
    template_folder='templates')


@home_bp.route("/", methods=['GET', 'POST'])
@home_bp.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():

    #Motivation
    file = os.path.join(app.root_path, 'static/motivation.json')

    if request.method == "POST":
        print(request.form.get("new_motivation_goal").replace(",","."))
        motivation = {
            'motivation_done': request.form.get("new_motivation_done").replace(",","."),
            'motivation_goal': request.form.get("new_motivation_goal").replace(",",".")
        }

        try:
            with open(file, 'w') as json_file:
                json.dump(motivation, json_file)
        except Exception as e:
            flash(f' Fehler beim Speichern der Änderungen. (Datei-Schreiben) -> Logfile Eintrag: {datetime.now()}',
                'danger')
            app.logger.warning(f'Error writing file on {request.path}. Time: {datetime.now()}. Exception: {e}\n')

        return redirect(url_for('home_bp.dashboard'))

    try:
        with open(file, 'r') as json_file:
            motivation = json.loads(json_file.read())
    except Exception as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (Fehler beim Datei-Lesen) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'Error reading file on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    motivation_todo=str(float(motivation["motivation_goal"])-float(motivation["motivation_done"])).replace(".",",")

    motivation_todo_split=motivation_todo.split(',')

    if len(motivation_todo_split[0])>=4:
        motivation_todo_split[0]=(motivation_todo_split[0])[:len(motivation_todo_split[0])-3] + '.' + (motivation_todo_split[0])[len(motivation_todo_split[0])-3:]
    if len(motivation_todo_split[1])==1:
        motivation_todo_split[1]+='0'
    motivation_todo=motivation_todo_split[0]+ ',' + motivation_todo_split[1] +' €'
    #Umlaufvermögen:
    try:
        results = db.session.execute('''SELECT SUM(amount*price) from item;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    if results[0] is not None:
        umlaufv=f'{str(results[0])[:-2]},{str(results[0])[-2:]} €'
    else:
        umlaufv='0,00 €'

    #Anzahl Item-Einträge:
    try:
        results = db.session.execute('''SELECT item.state, count(*) as 'amount' FROM item WHERE item.id_sale IS NULL AND item.internal = 1 
                                    GROUP BY item.state ORDER BY item.state;''').fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    #inv_fkt = inv_fkt.anzahl
    item_amount = [0, 0, 0]  #fkt, reparierbar, ungeprüft
    for i in range(len(results)):
        item_amount[i] = results[i][1]

    #gesamtanzahl items:
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM item WHERE item.id_sale IS NULL AND item.internal = 1;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    item_amount_total = results.amount

    #internal repairs:
    #auch verkaufte
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM repair JOIN item ON item.id_repair = repair.repair_id 
                                        WHERE item.internal=1 AND item.id_sale IS NULL AND repair.state = 'abgeschlossen';''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    rep_closed = results.amount

    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM repair JOIN item ON item.id_repair = repair.repair_id 
                                        WHERE item.internal=1 AND item.id_sale IS NULL AND repair.state != 'abgeschlossen';''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    rep_open = results.amount

    #repair orders:
    order_amount=[0,0]
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM repair_order WHERE repair_order.state = "abgeschlossen" ;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    order_amount[1] = results.amount

    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM repair_order WHERE repair_order.state != "abgeschlossen";''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)
    order_amount[0] = results.amount

    #categories:
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM category;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)
    cat_amount = results.amount

    #Services:
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM service;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)
    service_amount = results.amount

    #Services:
    try:
        results = db.session.execute('''SELECT count(*) as 'amount' FROM user WHERE username != 'automatic' and username != 'deleted_user' ;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    user_amount = results.amount

    #zsf=1 ersatzteile
    stmt= '''SELECT category.spare_part_for, category.superior_category, item.state,
                                      count(*) as amount FROM item
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.spare_part_for != '' 
                                      AND category.spare_part_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1
                                      GROUP BY category.spare_part_for, category.superior_category,
                                      item.state
                                      ORDER BY category.spare_part_for, category.superior_category, item.state;'''
    try:
        sp_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    sp_header = ['Ersatzteil', 'Kategorie', 'Status', 'Einträge']

    stmt = '''SELECT count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.spare_part_for != '' 
                                      AND category.spare_part_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 ; '''

    try:
        results = db.session.execute(stmt).first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    sp_amount_total = results.amount

    stmt = '''SELECT item.state, count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.spare_part_for != '' 
                                      AND category.spare_part_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 
                                      GROUP BY item.state ORDER BY item.state; '''
    try:
        results = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    sp_amount = [0, 0, 0]  #fkt, reparierbar, ungeprüft
    for i in range(len(results)):
        sp_amount[i] = results[i][1]
    values_sp = [sp_amount[0], sp_amount[1], sp_amount[2]]

    #zsf=1 zubehoer

    stmt = '''SELECT category.accessory_for, category.superior_category, item.state, count(*) as Anzahl
                                      FROM item INNER JOIN category ON item.id_category = category.category_id
                                      WHERE category.accessory_for != '' 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1
                                      AND category.accessory_for IS NOT NULL GROUP BY category.accessory_for,
                                      category.superior_category, item.state 
                                      ORDER BY category.accessory_for, category.superior_category, item.state;'''
    try:
        ac_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    ac_header = ['Zubehör', 'Kategorie', 'Status', 'Einträge']

    stmt = '''SELECT count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE category.accessory_for != '' 
                                      AND category.accessory_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 ; '''
    try:
        results = db.session.execute(stmt).first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    ac_amount_total = results.amount

    stmt = '''SELECT item.state, count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.accessory_for != '' 
                                      AND category.accessory_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 
                                      GROUP BY item.state ORDER BY item.state; '''

    try:
        results = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    ac_amount = [0, 0, 0]  #fkt, reparierbar, ungeprüft
    for i in range(len(results)):
        ac_amount[i] = results[i][1]
    values_ac = [ac_amount[0], ac_amount[1], ac_amount[2]]


    #zsf=1 sonstiges
    stmt = '''SELECT category.superior_category, item.state, count(*) as Anzahl FROM item
                                         INNER JOIN category ON item.id_category = category.category_id 
                                         WHERE category.spare_part_for = '' AND category.accessory_for ='' 
                                         AND item.id_sale IS NULL
                                         AND item.internal = 1
                                         GROUP BY category.superior_category, item.state 
                                         ORDER BY category.superior_category, item.state;'''

    try:
        other_content = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    other_header = ['Kategorie', 'Status', 'Einträge']

    stmt= '''SELECT count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.spare_part_for = '' AND category.accessory_for ='' 
                                      AND category.spare_part_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 ; '''
    try:
        results = db.session.execute(stmt).first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    a_amount_total = results.amount

    stmt = '''SELECT item.state, count(*) as 'amount' from item 
                                      INNER JOIN category ON item.id_category = category.category_id 
                                      WHERE  category.spare_part_for = '' AND category.accessory_for ='' 
                                      AND category.accessory_for IS NOT NULL 
                                      AND item.id_sale IS NULL
                                      AND item.internal = 1 
                                      GROUP BY item.state ORDER BY item.state; '''

    try:
        results = db.session.execute(stmt).fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    a_amount = [0, 0, 0]  #fkt, reparierbar, ungeprüft
    for i in range(len(results)):
        a_amount[i] = results[i][1]
    values_a = [a_amount[0], a_amount[1], a_amount[2]]

    #purchase / sales:

    try:
        results = db.session.execute('''SELECT count(*) as 'amount', sum(price) as 'sales_price' from sale;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    sales_count = results.amount
    sales_total = results.sales_price

    if sales_total is None:
        sales_total = '0.00'
    else:
        sales_total = round(sales_total, 2)

    try:
        results = db.session.execute('''SELECT count(*) as 'amount', sum(price) as 'purchase_price' from purchase;''').first()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    purchase_count = results.amount
    purchase_total = results.purchase_price
    if purchase_total is None:
        purchase_total = '0.00'
    else:
        purchase_total = round(purchase_total, 2)

    #graph:
    try:
        results_s = db.session.execute('''SELECT sum(price) as 'price', year(date) as 'year', month(date) as 'month' FROM sale GROUP BY year(date), month(date) ORDER BY year(date), month(date);''').fetchall()
        results_p = db.session.execute('''SELECT sum(price) as 'price', year(date) as 'year', month(date) as 'month' FROM purchase GROUP BY year(date), month(date) ORDER BY year(date), month(date);''').fetchall()
    except SQLAlchemyError as e:
        flash(f' Fehler bei der Darstellung des Dashboards. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}',
            'danger')
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        return render_template("dashboard.html", display_error=True)

    if not results_p or not results_s:
        return render_template("dashboard.html", user=flask_login.current_user.username, inv_fkt=item_amount,
                               inv_total=item_amount_total, rep_open=rep_open,
                               rep_closed=rep_closed, best_anz=order_amount, cat_amount=cat_amount,
                               sp_amount=sp_amount_total,
                               ac_amount=ac_amount_total, a_amount=a_amount_total, sales_total=sales_total,
                               sales_count=sales_count,
                               purchase_total=purchase_total, purchase_count=purchase_count,
                               service_amount=service_amount, user_amount=user_amount,
                               et_header=sp_header, et_content=sp_content, zb_content=ac_content,
                               zb_header=ac_header, sonst_header=other_header, sonst_content=other_content,
                               values_sp=values_sp,
                               values_ac=values_ac, values_a=values_a, umlaufv=umlaufv,
                               motivation_done=motivation["motivation_done"].replace(".",","),
                               motivation_goal=motivation["motivation_goal"].replace(".",","), motivation_todo=motivation_todo)

    #labels_p_s=labels, purchase_values=purchase_values, sale_values=sale_values,


    first_year = min(results_p[0].year, results_s[0].year)

    #is also first month of first year
    first_month = min(results_p[0].month, results_s[0].month)

    #first month of first year
    current_month = datetime.now().month
    current_year = datetime.now().year

    labels = []
    sale_values = []
    purchase_values = []

    if first_year != current_year:
    #first year registert in database
        for month in range(first_month, 13):
            labels.append(f"{first_year}-{month}")
            #check whether month, year combi is in sale group
            price=0.00
            for sale_group in results_s:
                if sale_group.year == first_year and sale_group.month == month:
                    price = sale_group.price

            sale_values.append(price)

            #check whether month, year combi is in purchase group
            price = 0.00
            for purchase_group in results_p:
                if purchase_group.year == first_year and purchase_group.month == month:
                    price = purchase_group.price

            purchase_values.append(price)

            # is month and year in s and p ?

        for year in range(first_year+1, current_year):
            for month in range(1,13):
                labels.append(f"{year}-{month}")

                price = 0.00

                for sale_group in results_s:

                    if sale_group.year == year and sale_group.month == month:
                        price = sale_group.price
                sale_values.append(price)

                price = 0.00

                for purchase_group in results_p:
                    if purchase_group.year == year and purchase_group.month == month:
                        price = purchase_group.price

                purchase_values.append(price)
        start_month = 1
    else:
        start_month=first_month
    #last year registered in database
    for month in range(start_month, current_month+1):
        labels.append(f"{current_year}-{month}")

        price = 0.00
        for sale_group in results_s:
            if sale_group.year == current_year and sale_group.month == month:
                price = sale_group.price

        sale_values.append(price)
        price = 0.00
        for purchase_group in results_p:
            if purchase_group.year == current_year and purchase_group.month == month:
                price = purchase_group.price
        purchase_values.append(price)


    for idx, val in enumerate(labels):
        labels[idx]=f'\'{val}\''
        print(f'{val}- {purchase_values[idx]}, {sale_values[idx]}')

    return render_template("dashboard.html", user=flask_login.current_user.username, inv_fkt=item_amount, inv_total=item_amount_total, rep_open=rep_open,
                           rep_closed=rep_closed, best_anz=order_amount, cat_amount=cat_amount, sp_amount=sp_amount_total,
                           ac_amount=ac_amount_total, a_amount = a_amount_total, sales_total=sales_total, sales_count= sales_count,
                           purchase_total=purchase_total, purchase_count=purchase_count,
                           service_amount=service_amount, user_amount= user_amount, labels_p_s=labels,
                           purchase_values=purchase_values, sale_values=sale_values,
                           et_header=sp_header, et_content=sp_content, zb_content=ac_content,
                           zb_header=ac_header, sonst_header=other_header, sonst_content=other_content, values_sp=values_sp,
                           values_ac=values_ac, values_a = values_a, umlaufv=umlaufv, motivation_done=motivation["motivation_done"].replace(".",","), motivation_goal=motivation["motivation_goal"].replace(".",","),
                           motivation_todo=motivation_todo)

