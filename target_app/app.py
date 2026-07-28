"""Flask 电商演示系统 — 用作自动化测试框架的"被测系统" """
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import User, PRODUCTS, CATEGORIES, CartItem, Order

app = Flask(__name__)
app.secret_key = "test-ecommerce-secret-key-2024"

# ============ 内存数据存储 ============
_users = {
    "testuser": User("testuser", "password123", "test@example.com"),
    "admin": User("admin", "admin123", "admin@example.com"),
}
_orders = []


def get_cart():
    """获取当前购物车"""
    cart = session.get("cart", {})
    items = []
    for pid, qty in cart.items():
        if pid in PRODUCTS:
            items.append(CartItem(pid, qty))
    return items


def cart_total(items):
    return sum(PRODUCTS[i.product_id].price * i.quantity for i in items)


@app.route("/")
def index():
    """商品列表 / 搜索页"""
    keyword = request.args.get("keyword", "").strip()
    category = request.args.get("category", "全部")

    products = list(PRODUCTS.values())

    if keyword:
        products = [p for p in products if keyword.lower() in p.name.lower()]
    if category != "全部":
        products = [p for p in products if p.category == category]

    return render_template("index.html", products=products, categories=CATEGORIES,
                           keyword=keyword, selected_category=category)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not username or not password:
            flash("用户名和密码不能为空", "error")
            return render_template("login.html")

        user = _users.get(username)
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash(f"欢迎回来，{user.username}！", "success")
            return redirect(url_for("index"))
        else:
            flash("用户名或密码错误", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已安全退出", "success")
    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    cart_items = get_cart()
    total = cart_total(cart_items)
    return render_template("cart.html", items=cart_items,
                           products=PRODUCTS, total=total)


@app.route("/cart/add", methods=["POST"])
def cart_add():
    product_id = request.form.get("product_id")
    if product_id not in PRODUCTS:
        flash("商品不存在", "error")
        return redirect(url_for("index"))

    product = PRODUCTS[product_id]
    if product.stock <= 0:
        flash(f"'{product.name}' 库存不足", "error")
        return redirect(url_for("index"))

    cart = session.get("cart", {})
    current_qty = cart.get(product_id, 0)
    if current_qty + 1 > product.stock:
        flash(f"'{product.name}' 库存不足 (库存: {product.stock})", "error")
        return redirect(url_for("index"))

    cart[product_id] = current_qty + 1
    session["cart"] = cart
    flash(f"已将 '{product.name}' 加入购物车", "success")
    return redirect(url_for("cart"))


@app.route("/cart/update", methods=["POST"])
def cart_update():
    product_id = request.form.get("product_id")
    action = request.form.get("action")
    cart = session.get("cart", {})

    if product_id not in cart:
        flash("商品不在购物车中", "error")
        return redirect(url_for("cart"))

    if action == "increase":
        product = PRODUCTS[product_id]
        if cart[product_id] + 1 > product.stock:
            flash(f"库存不足 (库存: {product.stock})", "error")
        else:
            cart[product_id] += 1
    elif action == "decrease":
        if cart[product_id] <= 1:
            del cart[product_id]
        else:
            cart[product_id] -= 1

    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/delete", methods=["POST"])
def cart_delete():
    product_id = request.form.get("product_id")
    cart = session.get("cart", {})
    if product_id in cart:
        del cart[product_id]
        session["cart"] = cart
        flash("已从购物车移除", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        flash("请先登录后再下单", "error")
        return redirect(url_for("login"))

    cart_items = get_cart()
    if not cart_items:
        flash("购物车为空，请先添加商品", "error")
        return redirect(url_for("cart"))

    total = cart_total(cart_items)

    if request.method == "POST":
        address = request.form.get("address", "").strip()
        payment = request.form.get("payment", "")

        if not address:
            flash("请填写收货地址", "error")
            return render_template("checkout.html", items=cart_items,
                                   products=PRODUCTS, total=total)

        items_summary = [
            {"product_name": PRODUCTS[ci.product_id].name,
             "quantity": ci.quantity,
             "price": PRODUCTS[ci.product_id].price}
            for ci in cart_items
        ]

        order = Order(session["user_id"], items_summary, address, payment, total)
        _orders.append(order)

        # 扣减库存
        for ci in cart_items:
            PRODUCTS[ci.product_id].stock -= ci.quantity

        session["cart"] = {}
        flash(f"订单提交成功！订单号: {order.id}", "success")
        return redirect(url_for("order_detail", order_id=order.id))

    return render_template("checkout.html", items=cart_items,
                           products=PRODUCTS, total=total)


@app.route("/order/<order_id>")
def order_detail(order_id):
    if "user_id" not in session:
        flash("请先登录", "error")
        return redirect(url_for("login"))
    order = next((o for o in _orders if o.id == order_id), None)
    if not order or order.user_id != session["user_id"]:
        flash("订单不存在", "error")
        return redirect(url_for("index"))
    return render_template("order.html", order=order)


@app.route("/api/products")
def api_products():
    """供测试框架获取商品数据"""
    return jsonify([
        {"id": p.id, "name": p.name, "category": p.category,
         "price": p.price, "stock": p.stock}
        for p in PRODUCTS.values()
    ])


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("=" * 50)
    print("  电商演示系统启动")
    print(f"  访问地址: http://localhost:5000")
    print(f"  测试账号: testuser / password123")
    print("=" * 50)
    app.run(debug=True, port=5000)
