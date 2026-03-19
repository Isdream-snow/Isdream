from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)
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
                date DATE NOT NULL DEFAULT (date('now'))
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # 处理上传数据
        name = request.form['name']
        distance = float(request.form['distance'])
        time = float(request.form['time'])
        date = request.form.get('date')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rides (name, distance, time, date) 
            VALUES (?, ?, ?, ?)
        ''',(name, distance, time, date))
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": "数据提交成功！"
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
        SELECT name, distance, time, date, (60*distance / time) AS speed 
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
    
    return jsonify([{
        'name': row[0],
        'distance': row[1],
        'time': row[2],
        'date': row[3],
        'speed': row[4] 
    } for row in results])

if __name__ == '__main__':
    app.run(debug=True)
