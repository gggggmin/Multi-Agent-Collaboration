"""电商系统数据模型"""
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class User:
    def __init__(self, username, password, email=""):
        self.id = str(uuid.uuid4())[:8]
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.email = email

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product:
    def __init__(self, id, name, category, price, stock, description=""):
        self.id = id
        self.name = name
        self.category = category
        self.price = price
        self.stock = stock
        self.description = description


class CartItem:
    def __init__(self, product_id, quantity=1):
        self.product_id = product_id
        self.quantity = quantity


class Order:
    def __init__(self, user_id, items, address, payment_method, total):
        self.id = str(uuid.uuid4())[:12]
        self.user_id = user_id
        self.items = items
        self.address = address
        self.payment_method = payment_method
        self.total = total
        self.status = "pending"
        self.created_at = datetime.now().isoformat()


# 预置商品数据
PRODUCTS = {
    "p001": Product("p001", "华为MateBook X Pro", "笔记本", 8999.00, 10),
    "p002": Product("p002", "Apple MacBook Air M3", "笔记本", 10999.00, 5),
    "p003": Product("p003", "ThinkPad X1 Carbon", "笔记本", 12999.00, 0),
    "p004": Product("p004", "iPhone 16 Pro", "手机", 8999.00, 20),
    "p005": Product("p005", "Samsung Galaxy S25", "手机", 6999.00, 15),
    "p006": Product("p006", "小米14 Ultra", "手机", 5999.00, 25),
    "p007": Product("p007", "Sony WH-1000XM6", "耳机", 2999.00, 30),
    "p008": Product("p008", "AirPods Pro 3", "耳机", 1999.00, 0),
}

CATEGORIES = ["全部", "笔记本", "手机", "耳机"]
