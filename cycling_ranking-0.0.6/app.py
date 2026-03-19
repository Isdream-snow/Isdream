from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3
import hashlib
import os
import secrets 



ADMIN_PASSWORD = "ZUISHUAIleiting666"
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
DATABASE = 'database.db'

# 初始化数据库
def init_db():
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                distance REAL NOT NULL, 
                time REAL NOT NULL,      
                date DATE NOT NULL DEFAULT (date('now')),
                is_anonymous BOOLEAN DEFAULT 0, 
                anonymous_id TEXT      
            )
        ''')
        conn.commit()
        conn.close()

with app.app_context():
    init_db()
# 获取排行榜数据（按距离降序）
def get_ranking():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT name, distance, time, date FROM rides ORDER BY distance DESC')
    results = cursor.fetchall()
    conn.close()
    return results

# 修改原有的管理面板路由，添加登录检查
@app.route('/admin')
def admin_panel():
    """管理员面板主页"""
    # 1. 验证密码
    if not session.get('is_admin'):
        # 未登录，重定向到登录页
        return redirect('/admin/login')
    
    # 2. 获取所有数据
    conn = sqlite3.connect(DATABASE)
    # 按日期倒序排列，方便查看最新数据
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, distance, time, date, is_anonymous, anonymous_id 
        FROM rides 
        ORDER BY date DESC, id DESC
    ''')
    all_rides = cursor.fetchall()
    conn.close()
    
    # 3. 渲染管理模板
    return render_template('admin.html', rides=all_rides)
# 在 app.py 中添加新路由
@app.route('/admin/delete/<int:ride_id>', methods=['POST'])
def admin_delete(ride_id):
    """删除单条骑行记录"""
    # 1. 验证密码
    if not session.get('is_admin'):
        return jsonify({"success": False, "error": "未登录或会话已过期。"}), 403
    
    # 2. 执行删除
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM rides WHERE id = ?', (ride_id,))
        conn.commit()
        deleted = cursor.rowcount > 0  # 检查是否成功删除了行
    except Exception as e:
        deleted = False
        print(f"删除记录时出错: {e}")
    finally:
        conn.close()
    
    # 3. 返回结果
    if deleted:
        return jsonify({"success": True, "message": f"记录 ID {ride_id} 已删除。"})
    else:
        return jsonify({"success": False, "error": "删除失败，记录可能不存在。"})

# 添加登录页面路由
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录页面"""
    # 如果已经登录，直接跳转到管理面板
    if session.get('is_admin'):
        return redirect('/admin')
    
    error = None
    if request.method == 'POST':
        # 验证密码
        provided_pass = request.form.get('admin_pass')
        if provided_pass == ADMIN_PASSWORD:
            # 密码正确，设置session
            session['is_admin'] = True
            return redirect('/admin')
        else:
            error = "密码错误，请重试。"
    
    # GET请求 或 密码错误时，显示登录表单
    return render_template('admin_login.html', error=error)



@app.route('/admin/logout')
def admin_logout():
    """管理员登出"""
    session.pop('is_admin', None)  # 清除session
    return redirect('/admin/login')
# 在 app.py 中添加以下代码
@app.route('/user/<identifier>')
def user_stats(identifier):
    """个人骑行统计页面"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 1. 获取用户所有骑行记录
    cursor.execute('''
        SELECT date, distance, time, (60 * distance / time) as speed, 
            is_anonymous, anonymous_id, name
        FROM rides 
        WHERE (name = ? OR anonymous_id = ?) AND time > 0
        ORDER BY date DESC
    ''', (identifier, identifier))
    records = cursor.fetchall()
    
    if not records:
        # 如果没有记录，返回空统计
        return render_template('user_stats.html', 
                              name=identifier, 
                              has_data=False,
                              records=[])
    first_record = records[0]
    is_anonymous_user = first_record[4]  # is_anonymous 字段
    display_name = first_record[5] if is_anonymous_user else first_record[6]
    # 2. 计算基本统计
    total_distance = sum(r[1] for r in records)
    total_time = sum(r[2] for r in records)
    average_speed = total_distance / (total_time/60) if total_time > 0 else 0
    total_rides = len(records)
    
    # 3. 计算最佳记录
    best_distance = max(records, key=lambda x: x[1])[1] if records else 0
    best_speed = max(records, key=lambda x: x[3])[3] if records else 0
    
    # 4. 按月份分组统计
    monthly_stats = {}
    for record in records:
        date = record[0]
        year_month = date[:7]  # 格式: YYYY-MM
        
        if year_month not in monthly_stats:
            monthly_stats[year_month] = {
                'distance': 0,
                'time': 0,
                'count': 0,
                'avg_speed': 0
            }
        
        monthly_stats[year_month]['distance'] += record[1]
        monthly_stats[year_month]['time'] += record[2]
        monthly_stats[year_month]['count'] += 1
    
    # 计算月度平均速度
    for month in monthly_stats.values():
        if month['time'] > 0:
            month['avg_speed'] = month['distance'] / (month['time']/60)
    
    # 5. 计算每周骑行统计（用于图表）
    weekly_distance = []
    weekly_speed = []
    weekly_dates = []
    
    # 按时间排序（从早到晚）
    sorted_records = sorted(records, key=lambda x: x[0])
    
    # 每5次骑行作为一个数据点（避免图表过于密集）
    chunk_size = 5
    for i in range(0, len(sorted_records), chunk_size):
        chunk = sorted_records[i:i+chunk_size]
        if chunk:
            chunk_distance = sum(r[1] for r in chunk)
            chunk_time = sum(r[2] for r in chunk)
            chunk_speed = chunk_distance / (chunk_time/60) if chunk_time > 0 else 0
            
            weekly_distance.append(chunk_distance)
            weekly_speed.append(chunk_speed)
            weekly_dates.append(f"第{i//chunk_size+1}组")
    
    # 如果骑行次数太少，就每条记录作为一个点
    if len(sorted_records) < 5:
        weekly_distance = [r[1] for r in sorted_records]
        weekly_speed = [r[3] for r in sorted_records]
        weekly_dates = [r[0] for r in sorted_records]
    
    # 6. 格式化记录用于前端显示
    formatted_records = []
    for record in records:
        formatted_records.append({
            'date': record[0],
            'distance': record[1],
            'time': record[2],
            'speed': record[3]
        })
    
    conn.close()
    
    return render_template('user_stats.html',
                          name=display_name,
                          has_data=True,
                          total_distance=total_distance,
                          total_time=total_time,
                          average_speed=average_speed,
                          total_rides=total_rides,
                          best_distance=best_distance,
                          best_speed=best_speed,
                          records=formatted_records,
                          monthly_stats=monthly_stats,
                          weekly_distance=weekly_distance,
                          weekly_speed=weekly_speed,
                          weekly_dates=weekly_dates,
                          is_anonymous=is_anonymous_user)



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form['name']
        distance = float(request.form['distance'])
        time = float(request.form['time'])
        date = request.form.get('date')
        is_anonymous = request.form.get('is_anonymous') == '1'
        anonymous_id = None
        if is_anonymous:
            # 1. 生成固定匿名ID
            # 使用用户IP和盐值创建哈希，确保同一来源生成相同ID
            salt = "YOUR_APP_SECRET_SALT"  # 请替换为一个复杂的随机字符串
            user_ip = request.remote_addr or '0.0.0.0'
            raw_id = f"{salt}{user_ip}"
            
            # 取哈希值前8位，生成如“匿名骑士A1B2C3D4”
            hash_obj = hashlib.md5(raw_id.encode())
            hash_hex = hash_obj.hexdigest()[:8].upper()
            anonymous_id = f"匿名骑士{hash_hex}"
            
            # 2. 在数据库记录中，我们仍然保存真实姓名（用于内部管理），
            # 但会标记为匿名，并记录其匿名ID。
            # 注意：display_name 在查询结果中将被 anonymous_id 覆盖
        else:
            # 公开提交，anonymous_id 为 NULL
            anonymous_id = None
        # 处理上传数据
        
        
        display_name = name

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rides (name, distance, time, date, is_anonymous, anonymous_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''',(name, distance, time, date, 1 if is_anonymous else 0, anonymous_id))
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": "数据提交成功！"+ ("（已匿名）" if is_anonymous else "")
        })
    try:
        ranking = get_ranking()
    except sqlite3.OperationalError:
        ranking = []
    
    return render_template('index.html', ranking=ranking)

@app.route('/get_ranking')
def get_ranking_json():
    sort_by = request.args.get('sort_by', 'distance')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    init_db()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    base_query = '''
        SELECT name, 
        distance,
        time, 
        date, 
        (60*distance / time) AS speed,
        is_anonymous,
        anonymous_id
    FROM rides 
    WHERE time > 0
    '''
    conditions = []
    params = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    
    if conditions:
        base_query += " AND " + " AND ".join(conditions)
    if sort_by == 'distance':
        base_query += " ORDER BY distance DESC"
    elif sort_by == 'speed':
        base_query += " ORDER BY speed DESC"
    elif sort_by == 'date':
        base_query += " ORDER BY date DESC"
    else:
        base_query += " ORDER BY distance DESC"
        
    cursor.execute(base_query, params)
    results = cursor.fetchall()
    conn.close()
    
    formatted_results = []
    for row in results:
        name, distance, time, date, speed, is_anonymous, anonymous_id = row
        display_name = anonymous_id if is_anonymous else name
        
        formatted_results.append({
            'name': display_name,  # 前端看到的是处理后的显示名
            'original_name': name,  # 保留原名，可用于后端管理（可选）
            'is_anonymous': bool(is_anonymous),
            'distance': distance,
            'time': time,
            'date': date,
            'speed': speed
        })
    
    return jsonify(formatted_results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
