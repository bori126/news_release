# -*- coding: utf-8 -*-
"""数据库层：连接管理 + 建库初始化"""
import os
import sqlite3

from flask import g
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "campus.db")
PAGE_SIZE = 10


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db():
    """首次运行时建库并写入示例数据"""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            real_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',   -- admin / user
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category_id INTEGER,
            content TEXT NOT NULL,
            author TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'published',  -- published / draft
            is_top INTEGER NOT NULL DEFAULT 0,
            views INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );
        CREATE TABLE notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            publisher TEXT DEFAULT '',
            is_important INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'published',
            views INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    users = [
        ("admin", generate_password_hash("admin123"), "系统管理员", "admin@campus.edu.cn", "admin"),
        ("stu01", generate_password_hash("123456"), "张三", "stu01@campus.edu.cn", "user"),
    ]
    c.executemany("INSERT INTO users(username,password,real_name,email,role) VALUES(?,?,?,?,?)", users)
    cats = [("校园动态",), ("教务通知",), ("学工活动",), ("招聘信息",)]
    c.executemany("INSERT INTO categories(name) VALUES(?)", cats)
    news = [
        ("我校在全省大学生程序设计竞赛中获佳绩", 1,
         "近日，第X届全省大学生程序设计竞赛落下帷幕。\n我校代表队经过激烈角逐，共获得一等奖2项、二等奖5项、三等奖8项，创历史最好成绩。\n此次比赛充分展示了我校学生扎实的专业基础和良好的团队协作精神。", "教务处", 1, 128),
        ("图书馆新增自习空间，欢迎同学们使用", 1,
         "为满足同学们的学习需求，图书馆对三楼东侧区域进行改造，新增自习座位200个。\n开放时间：每日 7:00 - 22:30。\n请同学们自觉保持安静，爱护公共设施。", "图书馆", 0, 96),
        ("春季运动会报名工作正式启动", 3,
         "一年一度的校春季运动会将于下月举行，即日起开始报名。\n报名方式：各班级体育委员统一汇总后报至学院体育部。\n报名截止时间：本月25日。", "校团委", 0, 75),
        ("计算机学院举办人工智能前沿讲座", 1,
         "本周五下午两点，学院特邀知名企业技术专家来校举办人工智能前沿技术讲座。\n地点：第一学术报告厅。\n欢迎对AI感兴趣的师生准时参加。", "计算机学院", 0, 54),
    ]
    c.executemany(
        "INSERT INTO news(title,category_id,content,author,is_top,views) VALUES(?,?,?,?,?,?)", news)
    notices = [
        ("关于2026届毕业生毕业设计选题的通知", "各位2026届毕业生：\n请于本月底前登录教务系统完成毕业设计选题，并与指导教师确认选题方向。\n逾期未选者由学院统一分配。", "教务处", 1, 210),
        ("校园网络系统升级维护公告", "为提升网络服务质量，信息中心定于本周六 0:00-6:00 对校园网核心设备进行升级维护，期间网络将出现短时中断，请师生提前做好安排。", "信息中心", 0, 87),
        ("关于开展学风建设月活动的通知", "学校决定开展为期一个月的学风建设活动，包括课堂考勤抽查、优秀学习笔记评选、学业帮扶结对等内容，请各学院认真组织落实。", "学生工作处", 0, 65),
    ]
    c.executemany(
        "INSERT INTO notices(title,content,publisher,is_important,views) VALUES(?,?,?,?,?)", notices)
    db.commit()
    db.close()
