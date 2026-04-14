#creds for auth elements: CoreyMSchafer
#https://github.com/CoreyMSchafer/code_snippets/blob/master/Python/Flask_Blog/

from application.auth.auth_func import save_picture, get_all_users
from flask import Blueprint, render_template, url_for, flash, redirect, request, session
from application import db, bcrypt, app
from application.forms import RegistrationForm, LoginForm, UpdateAccountForm, changePasswordForm
from application.models import User, item_table
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


auth_bp = Blueprint('auth_bp', __name__,
    template_folder = 'templates', url_prefix='')


#user id=0 -> "automatic"
#user id=1 -> "admin"
@auth_bp.route("/add_user", methods=['GET', 'POST'])
@login_required
def add_user():
    form = RegistrationForm()
    if form.validate_on_submit():

        try:
            user = User.query.filter_by(username=form.username.data).first()
        except SQLAlchemyError as e:
            flash(f'Der Benutzer konnte nicht hinzugefügt werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return render_template('register.html', title='Register', form=form)

        if user:
            flash('Dieser Benutzername wird bereits verwendet.', 'danger')
            return render_template('register.html', title='Register', form=form)

        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        try:
            user = User(username=form.username.data, password=hashed_password, image='default.jpg', admin_role=0)
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Der Benutzer konnte nicht hinzugefügt werden. (SQLAlchemy add() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy ADD exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return render_template('register.html', title='Register', form=form)

        flash('Benutzer wurde erstellt!', 'success')
        return redirect(url_for('auth_bp.user_management'))
    return render_template('register.html', title='Register', form=form)


@auth_bp.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home_bp.dashboard'))
    print(request.referrer)
    form = LoginForm()
    if form.validate_on_submit():

        try:
            user = User.query.filter_by(username=form.username.data).first()
        except SQLAlchemyError as e:
            flash(f'Anmeldung nicht möglich. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return render_template('login.html', title='Login', form=form)

        #deleted_user / automatic Anmeldung
        if user:
            if user.username == 'deleted_user' or user.username == 'automatic':
                flash('Anmeldung nicht möglich. Der ausgewählte Nutzer ist nicht dazu berechtigt.', 'danger')
                return render_template('login.html', title='Login', form=form)

        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            dest = request.args.get('next')
            if dest is None:
                dest = url_for('home_bp.dashboard')
            return redirect(dest)
        else:
            flash('Anmeldung nicht erfolgreich. Bitte überprüfe den angegebenen Benutzernamen und das Passwort.','danger')

    return render_template('login.html', title='Login', form=form)


@auth_bp.route("/logout")
def logout():

    #für repair_input, falls das Item bereits erstellt wurde, aber der user sich ausloggt, wird es hier gelöscht
    #toDo: selbes Spiel, falls der Browser geschlossen wird (on session.destroy or something)
    last_repair_input_page = session.get('last_repair_input_page')

    if last_repair_input_page and session.get('order_created') is False:

        #for some fucked up reason the last part contains no slash for repair_input_c_i_s
        # e.g.: http://localhost:5000/repair_input_c_i_s/1/27/1
        if "repair_input_c_i_s" in last_repair_input_page:
            url_list = last_repair_input_page.split("/")
            i_id = url_list[len(url_list) - 2]

            try:
                db.session.query(item_table).filter(item_table.item_id == i_id ).delete()
                db.session.commit()
                app.logger.warning(f'Item aus nicht abgeschlossener Auftrag Erstellung wurde gelöscht. ID: {i_id} Time: {datetime.now()}.')
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy DELETE exception on logout. Time: {datetime.now()}. Exception: {e}\n')
                app.logger.warning(f'FATAL ERROR: Item Eintrag verwaist, durch nicht abgeschlossene Auftrag Erstellung. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}, ID: {i_id}')

        #e.g.: http://localhost:5000/repair_input_c_i/1/27/
        elif "repair_input_c_i" in last_repair_input_page:
            url_list = last_repair_input_page.split("/")
            i_id = url_list[len(url_list) - 2]
            try:
                db.session.query(item_table).filter(item_table.item_id == i_id).delete()
                db.session.commit()
                app.logger.warning(f'Item aus nicht abgeschlossener Auftrag Erstellung wurde gelöscht. ID: {i_id} Time: {datetime.now()}.')
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f'SQLAlchemy DELETE exception on logout. Time: {datetime.now()}. Exception: {e}\n')
                app.logger.warning(f'FATAL ERROR: Item Eintrag verwaist, durch nicht abgeschlossene Auftrag Erstellung. (SQLAlchemy delete() error) -> Logfile Eintrag: {datetime.now()}, ID: {i_id}')

    session.clear()
    logout_user()
    return redirect(url_for('auth_bp.login'))


@auth_bp.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit() and form.picture.data:

        try:
            picture_file = save_picture(form.picture.data)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('auth_bp.account'))

        try:
            current_user.image = picture_file
            db.session.commit()
        except SQLAlchemyError as e:
            flash(f'Profilbild konnte nicht aktualisiert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
            app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
            return redirect(url_for('auth_bp.account'))

        flash('Profilbild wurde aktualisiert.', 'success')
        return redirect(url_for('auth_bp.account'))

    image_file = url_for('static', filename='profile_pics/' + current_user.image)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


@auth_bp.route("/user_management", methods=['GET', 'POST'])
@login_required
def user_management():
    if current_user.admin_role != 1:
        return render_template("restricted.html")

    form = changePasswordForm()
    if request.method == 'POST':
        if "admin_rights" in request.form:
            u_id = request.form.get("admin_rights")
            if "remove_admin" in request.form:
                try:
                    stmt = update(User).where(User.user_id == u_id).values(admin_role=0)
                    db.session.execute(stmt)
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash(f' Admin-Rechte konnten nicht entfernt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                    app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("auth_bp.user_management"))
                flash("Admin-Rechte für den Benutzer wurden entfernt.", 'success')
                return redirect(url_for("auth_bp.user_management"))
            if "grant_admin" in request.form:
                try:
                    stmt = update(User).where(User.user_id == u_id).values(admin_role=1)
                    db.session.execute(stmt)
                    db.session.commit()
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash(f' Admin-Rechte konnten nicht hinzugefügt werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}',
                        'danger')
                    app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                    return redirect(url_for("auth_bp.user_management"))
                flash("Admin-Rechte für den Benutzer wurden hinzugefügt.", 'success')
                return redirect(url_for("auth_bp.user_management"))

        if "delete_user" in request.form:
            try:
                stmt = update(User).where(User.user_id == request.form.get("user_id")).values(username='deleted_user', admin_role=0, password='')
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Benutzer konnte nicht gelöscht werden. (SQLAlchemy update() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("auth_bp.user_management"))
            flash("Benutzer wurde gelöscht.", 'success')
            return redirect(url_for("auth_bp.user_management"))

       # if 'change_password' in request.form:

        if form.validate_on_submit():

            try:
                user = User.query.filter_by(user_id=request.form.get("user_id")).first()
            except SQLAlchemyError as e:
                flash(f' Passwort konnte nicht geändert werden. (SQLAlchemy query() error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.warning(f'SQLAlchemy QUERY exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("auth_bp.user_management"))

            if not (bcrypt.check_password_hash(user.password, form.old_password.data)):
                flash(f'Das eingegebene Passwort für {user.username} ist nicht korrekt.', 'danger')
                return redirect(url_for("auth_bp.user_management"))

            hashed_password = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8')

            try:
                stmt = update(User).where(User.user_id == user.user_id).values(password=hashed_password)
                db.session.execute(stmt)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f' Passwort konnte nicht geändert werden. (SQLAlchemy UPDATE error) -> Logfile Eintrag: {datetime.now()}', 'danger')
                app.logger.error(f'SQLAlchemy UPDATE exception on {request.path}. Time: {datetime.now()}. Exception: {e}\n')
                return redirect(url_for("auth_bp.user_management"))
            flash('Das Passwort wurde erfolgreich geändert.', 'success')
            return redirect(url_for("auth_bp.user_management"))
        else:
            flash("Daten validierung nicht erfolgreich.", 'danger')

    try:
        users = get_all_users()
    except Exception as e:
        flash(str(e), 'danger')
        return render_template("user_managment.html", users=None, form=form)
    return render_template("user_management.html", users=users, form=form)
