from . import db, Base, login_manager
from flask_login import UserMixin

category_table = Base.classes.category
item_table = Base.classes.item
repair_table = Base.classes.repair
repair_order_table = Base.classes.repair_order
customer_table = Base.classes.customer
spare_part_table = Base.classes.spare_part
warehouse_table = Base.classes.warehouse
service_table = Base.classes.service
sale_table = Base.classes.sale
purchase_table = Base.classes.purchase
online_upload_table = Base.classes.online_upload
shop_order_table = Base.classes.shop_order

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class User(db.Model, UserMixin):

    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    image = db.Column(db.String(100), nullable=False)
    admin_role = db.Column(db.Integer, nullable=False)

    def get_id(self):
        return self.user_id

    def __repr__(self):
        return f"User('{self.username}', '{self.password}', '{self.image}', '{self.admin_role}')"