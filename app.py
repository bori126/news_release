# -*- coding: utf-8 -*-
"""校园新闻及通知发布系统 - Flask + HTML + SQLite 课程设计"""
import os
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from db import DB_PATH, PAGE_SIZE, close_db, execute, init_db, query
from routes_admin import bp as admin_bp

app = Flask(__name__)
app.secret_key = "campus-news-2026-secret"
app.teardown_appcontext(close_db)
app.register_blueprint(admin_bp)

if not os.path.exists(DB_PATH):
    init_db()

APP_TITLE = "校园新闻及通知发布系统"


# ==================== 通用辅助 ====================
@app.context_processor
def inject_globals():
    user = None
    if "uid" in session:
        user = query("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
    return dict(current_user=user, app_title=APP_TITLE)


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            flash("请先登录", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def paginate(sql_count, sql_data, args, page):
    total = query(sql_count, args, one=True)[0]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), pages)
    rows = query(sql_data + " LIMIT ? OFFSET ?", args + (PAGE_SIZE, (page - 1) * PAGE_SIZE))
    return rows, total, page, pages


def login_user(row):
    session.clear()
    session["uid"] = row["id"]
    session["username"] = row["username"]


def current_user_role():
    row = query("SELECT role FROM users WHERE id=?", (session["uid"],), one=True)
    return row["role"] if row else None


# ==================== 用户端（前台） ====================
@app.route("/")
def index():
    news = query(
        "SELECT n.*, c.name AS cat FROM news n LEFT JOIN categories c ON n.category_id=c.id "
        "WHERE n.status='published' ORDER BY n.is_top DESC, n.created_at DESC LIMIT 6")
    notices = query(
        "SELECT * FROM notices WHERE status='published' ORDER BY is_important DESC, created_at DESC LIMIT 6")
    return render_template("index.html", news=news, notices=notices)


@app.route("/news")
def news_list():
    kw = request.args.get("kw", "").strip()
    cat = request.args.get("cat", "").strip()
    page = request.args.get("page", 1, type=int)
    cond, args = "WHERE n.status='published'", []
    if kw:
        cond += " AND n.title LIKE ?"
        args.append(f"%{kw}%")
    if cat:
        cond += " AND n.category_id=?"
        args.append(cat)
    rows, total, page, pages = paginate(
        "SELECT COUNT(*) FROM news n " + cond,
        "SELECT n.*, c.name AS cat FROM news n LEFT JOIN categories c ON n.category_id=c.id "
        + cond + " ORDER BY n.is_top DESC, n.created_at DESC", tuple(args), page)
    cats = query("SELECT * FROM categories")
    return render_template("news.html", news=rows, cats=cats, kw=kw, cat=cat,
                           page=page, pages=pages, total=total)


@app.route("/news/<int:nid>")
def news_detail(nid):
    item = query("SELECT n.*, c.name AS cat FROM news n LEFT JOIN categories c ON n.category_id=c.id "
                 "WHERE n.id=? AND n.status='published'", (nid,), one=True)
    if not item:
        abort(404)
    execute("UPDATE news SET views=views+1 WHERE id=?", (nid,))
    hot = query("SELECT id,title FROM news WHERE status='published' AND id<>? "
                "ORDER BY views DESC LIMIT 5", (nid,))
    return render_template("news_detail.html", item=item, hot=hot)


@app.route("/notices")
def notice_list():
    kw = request.args.get("kw", "").strip()
    page = request.args.get("page", 1, type=int)
    cond, args = "WHERE status='published'", []
    if kw:
        cond += " AND title LIKE ?"
        args.append(f"%{kw}%")
    rows, total, page, pages = paginate(
        "SELECT COUNT(*) FROM notices " + cond,
        "SELECT * FROM notices " + cond + " ORDER BY is_important DESC, created_at DESC",
        tuple(args), page)
    return render_template("notices.html", notices=rows, kw=kw, page=page, pages=pages, total=total)


@app.route("/notices/<int:nid>")
def notice_detail(nid):
    item = query("SELECT * FROM notices WHERE id=? AND status='published'", (nid,), one=True)
    if not item:
        abort(404)
    execute("UPDATE notices SET views=views+1 WHERE id=?", (nid,))
    return render_template("notice_detail.html", item=item)


# ==================== 认证 ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = query("SELECT * FROM users WHERE username=?", (username,), one=True)
        if row and check_password_hash(row["password"], password):
            login_user(row)
            flash("登录成功", "ok")
            return redirect(url_for("admin.dashboard" if row["role"] == "admin" else "index"))
        flash("用户名或密码错误", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        real_name = request.form.get("real_name", "").strip()
        email = request.form.get("email", "").strip()
        if not username or not password:
            flash("用户名和密码不能为空", "error")
        elif len(password) < 6:
            flash("密码长度至少 6 位", "error")
        elif password != confirm:
            flash("两次输入的密码不一致", "error")
        elif query("SELECT id FROM users WHERE username=?", (username,), one=True):
            flash("用户名已存在", "error")
        else:
            execute("INSERT INTO users(username,password,real_name,email,role) VALUES(?,?,?,?,?)",
                    (username, generate_password_hash(password), real_name, email, "user"))
            flash("注册成功，请登录", "ok")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "ok")
    return redirect(url_for("login"))


# ==================== 个人中心（通用） ====================
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    base = "admin_base.html" if current_user_role() == "admin" else "user_base.html"
    if request.method == "POST":
        real_name = request.form.get("real_name", "").strip()
        email = request.form.get("email", "").strip()
        execute("UPDATE users SET real_name=?, email=? WHERE id=?",
                (real_name, email, session["uid"]))
        flash("个人信息保存成功", "ok")
        return redirect(url_for("profile"))
    user = query("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
    return render_template("profile.html", base=base, user=user)


@app.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    old = request.form.get("old_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm", "")
    user = query("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
    if not check_password_hash(user["password"], old):
        flash("原密码错误", "error")
    elif len(new) < 6:
        flash("新密码长度至少 6 位", "error")
    elif new != confirm:
        flash("两次输入的新密码不一致", "error")
    else:
        execute("UPDATE users SET password=? WHERE id=?",
                (generate_password_hash(new), session["uid"]))
        flash("密码修改成功", "ok")
    return redirect(url_for("profile"))


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="无权访问该页面"), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="页面不存在"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
