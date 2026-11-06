from flask import Flask, render_template, request, redirect, url_for, jsonify
import psycopg2
import psycopg2.extras
from datetime import date
import os

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS FLEXIBLE
# ==========================================
def get_db_connection():
    url_nube = os.environ.get("DATABASE_URL")
    if url_nube:
        return psycopg2.connect(url_nube)
    host_nube = os.environ.get("DB_HOST")
    if host_nube:
        return psycopg2.connect(
            host=host_nube, database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"), password=os.environ.get("DB_PASS")
        )
    return psycopg2.connect(host="localhost", database="parqueadero_db", user="postgres", password="nuenama159")

def add_column_safe(conn, cur, table, column, definition):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
        conn.commit()
    except Exception:
        conn.rollback()

# ==========================================
# RUTA 1: MAPA VISUAL DEL PARQUEADERO
# ==========================================
@app.route('/')
def mapa_parqueadero():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT c.id_celda, c.codigo_celda, c.estado, c.tipo, m.matricula 
        FROM celdas c
        LEFT JOIN movimientos m ON c.id_celda = m.id_celda AND m.estado_movimiento = 'en_parqueadero'
        ORDER BY c.id_celda ASC;
    """)
    celdas = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('mapa.html', celdas=celdas)

# ==========================================
# RUTA 2: REGISTRO E INGRESO DE VEHÍCULO
# ==========================================
@app.route('/registro', methods=['GET', 'POST'])
def registrar_vehiculo():
    conn = get_db_connection()
    if request.method == 'POST':
        matricula = request.form['matricula'].upper()
        marca = request.form.get('marca', '')
        color = request.form.get('color', '')
        propietario = request.form.get('propietario', '')
        celular = request.form.get('celular', '')
        recibe = request.form.get('recibe', '')
        id_celda = request.form['id_celda']
        fecha_recepcion = request.form['fecha_recepcion']
        fecha_entrega = request.form['fecha_entrega']
        
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO vehiculos (matricula, marca, color, propietario, celular) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (matricula) DO UPDATE SET 
                marca = EXCLUDED.marca, color = EXCLUDED.color, 
                propietario = EXCLUDED.propietario, celular = EXCLUDED.celular;
            """, (matricula, marca, color, propietario, celular))
            
            cur.execute("""
                INSERT INTO movimientos (matricula, id_celda, fecha_hora_recepcion, fecha_hora_entrega, recibe)
                VALUES (%s, %s, %s, %s, %s);
            """, (matricula, id_celda, fecha_recepcion, fecha_entrega, recibe))
            
            cur.execute("UPDATE celdas SET estado = 'ocupada' WHERE id_celda = %s;", (id_celda,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('mapa_parqueadero'))
    
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id_celda, codigo_celda, tipo FROM celdas WHERE estado = 'libre' ORDER BY id_celda ASC;")
    celdas_libres = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('registro.html', celdas_libres=celdas_libres)

# ==========================================
# RUTA 3: PANEL DE ENTREGAS PENDIENTES
# ==========================================
@app.route('/entregas-pendientes')
def listado_entregas():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT m.id_movimiento, m.matricula, v.marca, v.propietario, v.celular, c.codigo_celda, m.fecha_hora_entrega, m.recibe
        FROM movimientos m
        JOIN vehiculos v ON m.matricula = v.matricula
        JOIN celdas c ON m.id_celda = c.id_celda
        WHERE m.estado_movimiento = 'en_parqueadero'
        ORDER BY m.fecha_hora_entrega ASC;
    """)
    entregas = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('entregas.html', entregas=entregas)

# ==========================================
# RUTA 4: ACCIÓN - MARCAR COMO ENTREGADO
# ==========================================
@app.route('/marcar-entregado/<int:id_movimiento>', methods=['POST'])
def marcar_entregado(id_movimiento):
    entrega = request.form.get('entrega', 'No especificado')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id_celda FROM movimientos WHERE id_movimiento = %s;", (id_movimiento,))
        resultado = cur.fetchone()
        if resultado:
            id_celda = resultado[0]
            cur.execute("UPDATE celdas SET estado = 'libre' WHERE id_celda = %s;", (id_celda,))
            cur.execute("UPDATE movimientos SET estado_movimiento = 'devuelto', entrega = %s WHERE id_movimiento = %s;", (entrega, id_movimiento))
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error al entregar: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('listado_entregas'))

# ==========================================
# RUTA 5: API Y SISTEMA DE ALERTAS 
# ==========================================
@app.route('/api/alertas')
def api_alertas():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT m.matricula, c.codigo_celda, m.fecha_hora_entrega
        FROM movimientos m
        JOIN celdas c ON m.id_celda = c.id_celda
        WHERE DATE(m.fecha_hora_entrega) <= CURRENT_DATE
        AND m.estado_movimiento = 'en_parqueadero';
    """)
    pendientes = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({
        "hay_entregas": len(pendientes) > 0,
        "cantidad": len(pendientes),
        "vehiculos": pendientes
    })

# ==========================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# ==========================================
with app.app_context():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS celdas (
                id_celda SERIAL PRIMARY KEY, codigo_celda VARCHAR(10) UNIQUE NOT NULL,
                estado VARCHAR(15) DEFAULT 'libre', tipo VARCHAR(20) DEFAULT 'interna'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehiculos (
                matricula VARCHAR(10) PRIMARY KEY, marca VARCHAR(50), color VARCHAR(30)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id_movimiento SERIAL PRIMARY KEY, matricula VARCHAR(10) REFERENCES vehiculos(matricula),
                id_celda INT REFERENCES celdas(id_celda), fecha_hora_recepcion TIMESTAMP NOT NULL,
                fecha_hora_entrega TIMESTAMP NOT NULL, estado_movimiento VARCHAR(20) DEFAULT 'en_parqueadero'
            );
        """)
        conn.commit()

        add_column_safe(conn, cur, 'vehiculos', 'propietario', 'VARCHAR(100)')
        add_column_safe(conn, cur, 'vehiculos', 'celular', 'VARCHAR(20)')
        add_column_safe(conn, cur, 'movimientos', 'recibe', 'VARCHAR(50)')
        add_column_safe(conn, cur, 'movimientos', 'entrega', 'VARCHAR(50)')
        add_column_safe(conn, cur, 'celdas', 'tipo', "VARCHAR(20) DEFAULT 'interna'")

        cur.execute("SELECT COUNT(*) FROM celdas;")
        if cur.fetchone()[0] < 140:
            for i in range(1, 21):
                cur.execute("INSERT INTO celdas (codigo_celda, tipo) VALUES (%s, 'interna') ON CONFLICT DO NOTHING;", (f"INT-{i:02d}",))
            for i in range(1, 121):
                cur.execute("INSERT INTO celdas (codigo_celda, tipo) VALUES (%s, 'externa') ON CONFLICT DO NOTHING;", (f"EXT-{i:03d}",))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Base de datos y 140 celdas listas.")
    except Exception as e:
        print(f"Error inicializando BD: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)