from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from . import app
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import Regexp, DataRequired, Length, EqualTo


#variables available in all templates
@app.context_processor
def inject_user():
    if current_user.is_authenticated:
        user_dict = {
            'user_id': current_user.user_id,
            'username': current_user.username,
            'image': current_user.image,
            'is_admin': current_user.admin_role,
        }
    else:
        user_dict = 0
    return dict(user_dict=user_dict)


class RegistrationForm(FlaskForm):
    username = StringField('Benutzername',
                           validators=[Regexp(r'^[\w.@+-]+$'), DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Passwort', validators=[Length(min=10, max=20), DataRequired()])
    confirm_password = PasswordField('Passwort bestätigen',
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('weiter')


class changePasswordForm(FlaskForm):
    old_password = PasswordField('aktuelles Passwort', validators=[DataRequired()])
    new_password = PasswordField('Neues Passwort', validators=[Length(min=10, max=20), DataRequired()])
    confirm_new_password = PasswordField('Neues Passwort bestätigen',
                                     validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Ändern')

class LoginForm(FlaskForm):
    username = StringField('Benutzername',
                           validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Passwort', validators=[DataRequired()])
    submit = SubmitField('weiter')


class UpdateAccountForm(FlaskForm):

    picture = FileField('Profilbild', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('aktualisieren')

   #def validate_username(self, username):
   #    if username.data != current_user.username:
