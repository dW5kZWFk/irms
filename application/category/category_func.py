from flask import request
from application import db, app
from application.models import category_table, item_table
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


def get_cat_id(c_sup_name, c_name, c_ac, c_sp):
    try:
        cat_id = db.session.query(category_table.category_id).filter(
                                    category_table.name == c_name,
                                    category_table.superior_category == c_sup_name,
                                    category_table.accessory_for == c_ac, category_table.spare_part_for == c_sp).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f' Fehler in "get_cat_id" (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return cat_id


#creates dictionary with top categories and according sub categories
#used to display categories in /products and /input_values
def create_cat_dict():
    cat_dict = {}

    try:
        # superior_categories
        for cat_top in db.session.query(category_table.superior_category).distinct():
            cat_top_val = cat_top.superior_category
            cat_bottom_list = []

            #-> names
            for name in db.session.query(category_table.name).filter(category_table.superior_category == cat_top_val).distinct():
                cat_bottom_list.append(name.name)

            cat_dict[cat_top_val] = cat_bottom_list
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("Fehler in create_cat_dict (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}")
    return cat_dict


#get full database entry for existing categories
def get_existing_categories(lvl1, lvl2, lvl3):

    if lvl1 == "alle":
        stmt = '''SELECT category.category_id, category.superior_category, category.name,
            category.accessory_for, category.spare_part_for, category.legal_descr FROM category;'''
    elif lvl1 == "anderes":
        if lvl2 == "alle":
            stmt = '''SELECT category.category_id, category.superior_category, category.name,
            category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
            WHERE (category.spare_part_for IS NULL OR category.spare_part_for = '') 
            AND (category.accessory_for IS NULL or category.accessory_for = '');'''
        else:
            stmt = f'''SELECT category.category_id, category.superior_category, category.name,
                        category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                        WHERE (category.spare_part_for IS NULL OR category.spare_part_for = '') 
                        AND (category.accessory_for IS NULL or category.accessory_for = '') 
                        AND category.superior_category = '{lvl2}';'''
    elif lvl1 == "ersatzteile":
        if lvl2 == "alle":
            stmt = '''SELECT category.category_id, category.superior_category, category.name,
                        category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                        WHERE (category.spare_part_for IS NOT NULL AND category.spare_part_for != '') 
                        AND (category.accessory_for IS NULL or category.accessory_for = '');'''
        elif lvl3 == "alle":
            stmt = f'''SELECT category.category_id, category.superior_category, category.name,
                                    category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                                    WHERE (category.spare_part_for = '{lvl2}') 
                                    AND (category.accessory_for IS NULL or category.accessory_for = '');'''
        else:
            stmt = f'''SELECT category.category_id, category.superior_category, category.name,
                                                category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                                                WHERE category.spare_part_for = '{lvl2}'
                                                AND category.superior_category = '{lvl3}'
                                                AND (category.accessory_for IS NULL or category.accessory_for = '');'''
    elif lvl1 == "zubehoer":
        if lvl2 == "alle":
            stmt = '''SELECT category.category_id, category.superior_category, category.name,
                        category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                        WHERE (category.spare_part_for IS NULL OR category.spare_part_for = '') 
                        AND (category.accessory_for IS NOT NULL AND category.accessory_for != '');'''
        elif lvl3 == "alle":
            stmt = f'''SELECT category.category_id, category.superior_category, category.name,
                                    category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                                    WHERE (category.spare_part_for IS NULL OR category.spare_part_for = '')  
                                    AND (category.accessory_for  = '{lvl2}');'''
        else:
            stmt = f'''SELECT category.category_id, category.superior_category, category.name,
                                                category.accessory_for, category.spare_part_for, category.legal_descr FROM category 
                                                WHERE (category.spare_part_for IS NULL OR category.spare_part_for = '') 
                                                AND category.superior_category = '{lvl3}'
                                                AND (category.accessory_for = '{lvl2}');'''

    try:
        all_categories = db.session.execute(stmt)
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception("Fehler in get_existing_categories (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}")


    c_list = []
    #find out whether category is part of none sold item
    for row in all_categories:
        row = list(row)

        try:
            item_results = db.session.query(item_table.item_id) \
                .filter(item_table.id_category == row[0], item_table.id_sale == None).first()
        except SQLAlchemyError as e:
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            raise Exception(f' Die Item-Daten konnten nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

        #category is not deletable when it is in an active item
        if item_results:
            row.insert(0, 'yes')
        else:
            row.insert(0, 'no')

        c_list.append(row)
    print(c_list)
    all_categories_labels_1 = ['ID', 'Top-Kategorie', 'Kategorie', 'Zubehör von', 'Ersatzteil Von']

    return c_list, all_categories_labels_1


def get_values_from_category_form():
    if request.form.get('top_kat_selection') == 'neu':
        superior_category = request.form.get('kategorie_input')
    else:
        superior_category = request.form.get('top_kat_selection')

    if request.form.get('zubehoer_selection') == 'neu':
        accessory_for = request.form.get('zubehoer_input')
    else:
        accessory_for = request.form.get('zubehoer_selection')

    if accessory_for is None:
        accessory_for = ''

    if request.form.get('ersatzteil_selection') == 'neu':
        spare_part_for = request.form.get('ersatzteil_input')
    else:
        spare_part_for = request.form.get('ersatzteil_selection')

    if spare_part_for is None:
        spare_part_for = ''

    return superior_category, accessory_for, spare_part_for


#accepts item id and returns legal description for category
def get_legal_descr(i_id):
    try:
        legal_descr = db.session.query(category_table.legal_descr).join(item_table).filter(item_table.item_id==i_id).first()
    except SQLAlchemyError as e:
        app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
        raise Exception(f'Der Rechtstext konnte nicht geladen werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}')

    return legal_descr.legal_descr