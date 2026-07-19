from flask import Flask, request, render_template_string, flash, redirect, url_for
import pymysql
from mcrcon import MCRcon
import os
import traceback

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# ========== 配置信息 ==========
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = os.getenv('DB_PASS', 'CHANGE_ME_DB_PASSWORD')
DB_NAME = 'mc_registry'

RCON_HOST = '127.0.0.1'
RCON_PORT = 25575
RCON_PASS = os.getenv('RCON_PASS', 'CHANGE_ME_RCON_PASSWORD')

# 白名单管理后台简易密码
ADMIN_PASS = os.getenv('ADMIN_PASS', 'CHANGE_ME_ADMIN_PASSWORD')

# ========== 前端页面 ==========

# 用户注册页（新增了一个"进入管理后台"链接）
HTML_FORM = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>我的世界 · 白名单自助注册</title>
    <style>
        body { font-family: Arial; max-width: 500px; margin: 50px auto; text-align: center; }
        input, button { padding: 10px; margin: 5px; width: 80%; }
        .msg { color: red; }
        .ok { color: green; }
    </style>
</head>
<body>
    <h2>✨ 输入游戏ID，自动加入白名单</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, msg in messages %}
                <p class="{{ category }}">{{ msg }}</p>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <form action="/register" method="post">
        <p><input type="text" name="mc_name" placeholder="你的Minecraft ID（必须精确）" required></p>
        <p><input type="text" name="username" placeholder="你的昵称（选填）"></p>
        <p><button type="submit">🚀 立即注册</button></p>
    </form>
    <p><a href="/admin">🔧 进入管理后台</a></p>
</body>
</html>
'''

# 白名单管理后台页
ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>管理后台 · 用户列表</title>
    <style>
        body { font-family: Arial; max-width: 900px; margin: 30px auto; padding: 0 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f4f4f4; }
        .btn-del { color: red; text-decoration: none; }
        .btn-del:hover { text-decoration: underline; }
        .back { margin-top: 20px; display: inline-block; }
    </style>
</head>
<body>
    <h2>📋 已注册用户列表（共 {{ count }} 人）</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>昵称</th>
            <th>MC游戏ID</th>
            <th>注册时间</th>
            <th>操作</th>
        </tr>
        {% for u in users %}
        <tr>
            <td>{{ u.id }}</td>
            <td>{{ u.username or '-' }}</td>
            <td>{{ u.mc_name }}</td>
            <td>{{ u.registered_at }}</td>
            <td><a class="btn-del" href="/admin/delete/{{ u.id }}?pwd={{ pwd }}" onclick="return confirm('确定删除 {{ u.mc_name }}？')">🗑️ 删除</a></td>
        </tr>
        {% endfor %}
    </table>
    <a class="back" href="/">⬅️ 返回注册页</a>
</body>
</html>
'''

# ========== 接口 ==========

@app.route('/')
def index():
    return render_template_string(HTML_FORM)

@app.route('/register', methods=['POST'])
def register():
    mc_name = request.form.get('mc_name').strip()
    username = request.form.get('username').strip() or mc_name

    if not mc_name:
        flash('游戏ID不能为空！', 'msg')
        return redirect(url_for('index'))

    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, mc_name) VALUES (%s, %s)", (username, mc_name))
        conn.commit()
        cursor.close()
        conn.close()
    except pymysql.err.IntegrityError:
        flash(f'❌ 玩家 "{mc_name}" 已经注册过了，请勿重复提交！', 'msg')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'❌ 数据库连接失败，请检查配置: {e}', 'msg')
        return redirect(url_for('index'))

    try:
        mcr = MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT)
        mcr.connect()
        resp = mcr.command(f'owhitelist add name {mc_name}')
        mcr.command('reload')
        mcr.disconnect()
        print(f"[RCON] 添加成功: {resp}")
    except Exception as e:
        print("="*50)
        print("RCON 连接/执行失败，详细报错如下：")
        traceback.print_exc()
        print("="*50)
        flash(f'⚠️ 数据库已记录，但白名单添加失败（RCON未连接）: {e}', 'msg')
        return redirect(url_for('index'))

    flash(f'✅ 恭喜 "{mc_name}"，白名单添加成功！请重启游戏或输入 /reload 生效。', 'ok')
    return redirect(url_for('index'))

# ========== 管理白名单网页后台接口 ==========

@app.route('/admin')
def admin_list():
    """用户列表页"""
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        cursor = conn.cursor(pymysql.cursors.DictCursor)  # 字典格式，模板直接读字段名
        cursor.execute("SELECT id, username, mc_name, registered_at FROM users ORDER BY id DESC")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template_string(ADMIN_HTML, users=users, count=len(users), pwd=request.args.get('pwd',''))
    except Exception as e:
        return f"数据库查询失败: {e}", 500

@app.route('/admin/delete/<int:user_id>')
def admin_delete(user_id):
    """删除用户：DB记录 + RCON同步移除白名单"""
    pwd = request.args.get('pwd', '')
    if pwd != ADMIN_PASS:
        return "权限验证失败", 403

    # 1. 先查出 mc_name
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT mc_name FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return "用户不存在", 404
        mc_name = row[0]

        # 2. 删除DB记录
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return f"数据库操作失败: {e}", 500

    # 3. RCON移除白名单（适配 OriginXWhitelist 插件）
    try:
        mcr = MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT)
        mcr.connect()
        resp = mcr.command(f'owhitelist remove name {mc_name}')
        mcr.command('reload')
        mcr.disconnect()
        print(f"[RCON] 移除成功: {resp}")
    except Exception as e:
        traceback.print_exc()
        return f"数据库已删除，但RCON移除失败（请手动执行 owhitelist remove name {mc_name}）: {e}", 500

    return redirect(url_for('admin_list', pwd=pwd))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=False)
