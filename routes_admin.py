# -*- coding: utf-8 -*-
"""管理端（后台）路由：仪表盘 / 新闻管理 / 通知管理 / 分类管理 / 用户管理"""
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import generate_password_hash

from db import PAGE_SIZE, execute, query

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return redirect(url_for("login"))
        row = query("SELECT role FROM users WHERE id=?", (session["uid"],), one=True)
        if not row or row["role"] != "admin":
            abort(403)
        return f(*a, **kw)
    return wrapper


@bp.context_processor
def inject_active():
    return dict(active=request.endpoint)


@bp.route("/")
@admin_required
def dashboard():
    stats = {
        "news": query("SELECT COUNT(*) FROM news", one=True)[0],
        "notices": query("SELECT COUNT(*) FROM notices", one=True)[0],
        "users": query("SELECT COUNT(*) FROM users", one=True)[0],
        "views": query("SELECT IFNULL(SUM(views),0) FROM news", one=True)[0]
                 + query("SELECT IFNULL(SUM(views),0) FROM notices", one=True)[0],
    }
    latest_news = query("SELECT n.*, c.name AS cat FROM news n LEFT JOIN categories c "
                        "ON n.category_id=c.id ORDER BY n.created_at DESC LIMIT 5")
    latest_notices = query("SELECT * FROM notices ORDER BY created_at DESC LIMIT 5")
    return render_template("admin/dashboard.html", stats=stats,
                           latest_news=latest_news, latest_notices=latest_notices)


# ---------- 新闻管理 ----------
@bp.route("/news")
@admin_required
def news_list():
    kw = request.args.get("kw", "").strip()
    page = request.args.get("page", 1, type=int)
    cond, args = "", []
    if kw:
        cond = "WHERE n.title LIKE ?"
        args.append(f"%{kw}%")
    total = query(f"SELECT COUNT(*) FROM news n {cond}", args, one=True)[0]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), pages)
    rows = query(
        f"SELECT n.*, c.name AS cat FROM news n LEFT JOIN categories c ON n.category_id=c.id "
        f"{cond} ORDER BY n.is_top DESC, n.created_at DESC LIMIT ? OFFSET ?",
        args + [PAGE_SIZE, (page - 1) * PAGE_SIZE])
    return render_template("admin/news_list.html", news=rows, kw=kw, page=page, pages=pages, total=total)


def _save_news(nid=None):
    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id") or None
    content = request.form.get("content", "").strip()
    author = request.form.get("author", "").strip()
    status = request.form.get("status", "published")
    is_top = 1 if request.form.get("is_top") else 0
    if not title or not content:
        flash("标题和内容不能为空", "error")
        return False
    if nid:
        execute("UPDATE news SET title=?, category_id=?, content=?, author=?, status=?, is_top=? WHERE id=?",
                (title, category_id, content, author, status, is_top, nid))
        flash("新闻修改成功", "ok")
    else:
        execute("INSERT INTO news(title,category_id,content,author,status,is_top) VALUES(?,?,?,?,?,?)",
                (title, category_id, content, author, status, is_top))
        flash("新闻发布成功", "ok")
    return True


@bp.route("/news/add", methods=["GET", "POST"])
@admin_required
def news_add():
    if request.method == "POST" and _save_news():
        return redirect(url_for("admin.news_list"))
    cats = query("SELECT * FROM categories")
    return render_template("admin/news_form.html", cats=cats, item=None)


@bp.route("/news/edit/<int:nid>", methods=["GET", "POST"])
@admin_required
def news_edit(nid):
    if request.method == "POST" and _save_news(nid):
        return redirect(url_for("admin.news_list"))
    item = query("SELECT * FROM news WHERE id=?", (nid,), one=True)
    if not item:
        abort(404)
    cats = query("SELECT * FROM categories")
    return render_template("admin/news_form.html", cats=cats, item=item)


@bp.route("/news/delete/<int:nid>", methods=["POST"])
@admin_required
def news_delete(nid):
    execute("DELETE FROM news WHERE id=?", (nid,))
    flash("新闻已删除", "ok")
    return redirect(url_for("admin.news_list"))


# ---------- 通知管理 ----------
@bp.route("/notices")
@admin_required
def notice_list():
    kw = request.args.get("kw", "").strip()
    page = request.args.get("page", 1, type=int)
    cond, args = "", []
    if kw:
        cond = "WHERE title LIKE ?"
        args.append(f"%{kw}%")
    total = query(f"SELECT COUNT(*) FROM notices {cond}", args, one=True)[0]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), pages)
    rows = query(f"SELECT * FROM notices {cond} ORDER BY is_important DESC, created_at DESC "
                 f"LIMIT ? OFFSET ?", args + [PAGE_SIZE, (page - 1) * PAGE_SIZE])
    return render_template("admin/notice_list.html", notices=rows, kw=kw, page=page, pages=pages, total=total)


def _save_notice(nid=None):
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    publisher = request.form.get("publisher", "").strip()
    is_important = 1 if request.form.get("is_important") else 0
    status = request.form.get("status", "published")
    if not title or not content:
        flash("标题和内容不能为空", "error")
        return False
    if nid:
        execute("UPDATE notices SET title=?, content=?, publisher=?, is_important=?, status=? WHERE id=?",
                (title, content, publisher, is_important, status, nid))
        flash("通知修改成功", "ok")
    else:
        execute("INSERT INTO notices(title,content,publisher,is_important,status) VALUES(?,?,?,?,?)",
                (title, content, publisher, is_important, status))
        flash("通知发布成功", "ok")
    return True


@bp.route("/notices/add", methods=["GET", "POST"])
@admin_required
def notice_add():
    if request.method == "POST" and _save_notice():
        return redirect(url_for("admin.notice_list"))
    return render_template("admin/notice_form.html", item=None)


@bp.route("/notices/edit/<int:nid>", methods=["GET", "POST"])
@admin_required
def notice_edit(nid):
    if request.method == "POST" and _save_notice(nid):
        return redirect(url_for("admin.notice_list"))
    item = query("SELECT * FROM notices WHERE id=?", (nid,), one=True)
    if not item:
        abort(404)
    return render_template("admin/notice_form.html", item=item)


@bp.route("/notices/delete/<int:nid>", methods=["POST"])
@admin_required
def notice_delete(nid):
    execute("DELETE FROM notices WHERE id=?", (nid,))
    flash("通知已删除", "ok")
    return redirect(url_for("admin.notice_list"))


# ---------- 分类管理 ----------
@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name and not query("SELECT id FROM categories WHERE name=?", (name,), one=True):
            execute("INSERT INTO categories(name) VALUES(?)", (name,))
            flash("分类添加成功", "ok")
        else:
            flash("分类名为空或已存在", "error")
        return redirect(url_for("admin.categories"))
    cats = query("SELECT c.*, COUNT(n.id) AS cnt FROM categories c "
                 "LEFT JOIN news n ON n.category_id=c.id GROUP BY c.id ORDER BY c.id")
    return render_template("admin/categories.html", cats=cats)


@bp.route("/categories/delete/<int:cid>", methods=["POST"])
@admin_required
def category_delete(cid):
    execute("DELETE FROM categories WHERE id=?", (cid,))
    flash("分类已删除", "ok")
    return redirect(url_for("admin.categories"))


# ---------- 用户管理 ----------
@bp.route("/users")
@admin_required
def users():
    kw = request.args.get("kw", "").strip()
    cond, args = "", []
    if kw:
        cond = "WHERE username LIKE ? OR real_name LIKE ?"
        args = [f"%{kw}%", f"%{kw}%"]
    rows = query(f"SELECT * FROM users {cond} ORDER BY id", args)
    return render_template("admin/users.html", users=rows, kw=kw)


@bp.route("/users/add", methods=["POST"])
@admin_required
def user_add():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    real_name = request.form.get("real_name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "user")
    if not username or len(password) < 6:
        flash("用户名不能为空，密码至少 6 位", "error")
    elif query("SELECT id FROM users WHERE username=?", (username,), one=True):
        flash("用户名已存在", "error")
    else:
        execute("INSERT INTO users(username,password,real_name,email,role) VALUES(?,?,?,?,?)",
                (username, generate_password_hash(password), real_name, email, role))
        flash("用户添加成功", "ok")
    return redirect(url_for("admin.users"))


@bp.route("/users/reset/<int:uid>", methods=["POST"])
@admin_required
def user_reset(uid):
    execute("UPDATE users SET password=? WHERE id=?",
            (generate_password_hash("123456"), uid))
    flash("密码已重置为 123456", "ok")
    return redirect(url_for("admin.users"))


@bp.route("/users/delete/<int:uid>", methods=["POST"])
@admin_required
def user_delete(uid):
    if uid == session["uid"]:
        flash("不能删除当前登录账号", "error")
    else:
        execute("DELETE FROM users WHERE id=?", (uid,))
        flash("用户已删除", "ok")
    return redirect(url_for("admin.users"))
