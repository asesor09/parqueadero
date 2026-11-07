from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import psycopg2
import psycopg2.extras
from datetime import date
import os
import traceback

app = Flask(__name__)

# ==========================================
# CONEXIÓN A BASE DE DATOS
# ==========================================
def get_db_connection():
    url_nube = os.environ.get("DATABASE_URL")
    if url_nube:
        return psycopg2.connect(url_nube)
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "parqueadero_db"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", "nuenama159")
    )

# ==========================================
# CÓDIGOS VISUALES (HTML) INCORPORADOS
# ==========================================
HTML_MAPA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Mapa Parqueadero</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 20px; margin: 0; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 15px; text-decoration: none; background: #333; color: white; padding: 10px 15px; border-radius: 5px; }
        .grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
        .celda { width: 90px; height: 90px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 8px; font-weight: bold; border: 2px solid #555; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); text-align: center; }
        .interna.libre { background-color: #90ee90; }
        .externa.libre { background-color: #add8e6; }
        .ocupada { background-color: #ffcccb; color: #a00; border-color: #a00; }
        .tipo-label { font-size: 0.7em; color: #555; margin-bottom: 5px; }
        #modal-alerta { display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.8); }
        .modal-contenido { background-color: #dc3545; color: white; margin: 10% auto; padding: 40px; border: 4px solid #fff; border-radius: 12px; width: 80%; max-width: 550px; text-align: center; box-shadow: 0px 0px 30px rgba(220, 53, 69, 0.9); animation: latido 1.2s infinite; }
        @keyframes latido { 0% { transform: scale(1); } 50% { transform: scale(1.04); } 100% { transform: scale(1); } }
        .btn-cerrar { background: white; color: #dc3545; padding: 10px 20px; font-weight: bold; border: none; cursor: pointer; border-radius: 5px; margin-top: 15px;}
        .btn-ir { display:inline-block; background:#ffeb3b; color:#333; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:5px; margin-right:10px;}
    </style>
</head>
<body>
    <h1>Mapa del Parqueadero</h1>
    
    <div id="modal-alerta">
        <div class="modal-contenido">
            <h2 style="margin-top:0;">🚨 ¡ATENCIÓN AL ENCARGADO! 🚨</h2>
            <p style="font-size: 1.3em;">Hay <strong><span id="num-alertas">0</span></strong> vehículo(s) programado(s) para salir hoy o con retraso.</p>
            <a href="/entregas-pendientes" class="btn-ir">Ver Lista de Entregas</a>
            <button class="btn-cerrar" onclick="document.getElementById('modal-alerta').style.display='none'">Cerrar Aviso</button>
        </div>
    </div>

    <div class="nav">
        <a href="/registro">Registrar Ingreso</a>
        <a href="/entregas-pendientes">Entregas y Salidas</a>
        <a href="/instalar" style="background:#007bff;">Reparar/Instalar Tablas</a>
    </div>

    <div class="grid">
        {% for celda in celdas %}
            <div class="celda {{ celda.tipo }} {{ celda.estado }}">
                <span class="tipo-label">{{ celda.tipo | upper }}</span>
                <span>{{ celda.codigo_celda }}</span>
                {% if celda.estado == 'ocupada' %}
                    <span style="margin-top: 5px; font-size: 0.8em;">🚗 {{ celda.matricula }}</span>
                {% endif %}
            </div>
        {% endfor %}
    </div>

    <script>
        fetch('/api/alertas')
            .then(response => response.json())
            .then(data => {
                if (data.hay_entregas) {
                    document.getElementById('modal-alerta').style.display = 'block';
                    document.getElementById('num-alertas').innerText = data.cantidad;
                }
            })
            .catch(error => console.error('Error:', error));
    </script>
</body>
</html>
"""

HTML_REGISTRO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Ingreso de Vehículo</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f4f4f9; }
        form { max-width: 500px; display: flex; flex-direction: column; gap: 15px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        input, select, button { padding: 10px; font-size: 1em; border-radius: 5px; border: 1px solid #ccc; }
        button { background-color: #28a745; color: white; border: none; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Registrar Ingreso</h1>
    <a href="/" style="display:inline-block; margin-bottom:20px; color: #007bff; text-decoration: none;">🔙 Volver al Mapa</a>

    <form method="POST">
        <input type="text" name="matricula" placeholder="Placa del Vehículo (Obligatorio)" required>
        <input type="text" name="marca" placeholder="Marca (Opcional)">
        <input type="text" name="color" placeholder="Color (Opcional)">
        <hr>
        <input type="text" name="propietario" placeholder="Nombre del Propietario (Opcional)">
        <input type="text" name="celular" placeholder="Número Celular (Opcional)">
        <input type="text" name="recibe" placeholder="Conductor que trae el carro (Opcional)">
        <hr>
        <select name="id_celda" required>
            <option value="">Seleccione una celda libre...</option>
            {% for celda in celdas_libres %}
                <option value="{{ celda.id_celda }}">{{ celda.codigo_celda }} ({{ celda.tipo | upper }})</option>
            {% endfor %}
        </select>
        <label>Fecha/Hora Recepción:</label>
        <input type="datetime-local" name="fecha_recepcion" required>
        <label>Fecha/Hora Promesa Entrega:</label>
        <input type="datetime-local" name="fecha_entrega" required>
        <button type="submit">Registrar Ingreso</button>
    </form>
</body>
</html>
"""

HTML_ENTREGAS = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel de Entregas</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f4f4f9; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #333; color: white; }
        .form-entrega { display: flex; gap: 5px; }
        .form-entrega input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        .btn-entregar { background-color: #007bff; color: white; border: none; padding: 8px 12px; cursor: pointer; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Vehículos en el Parqueadero</h1>
    <a href="/" style="color: #007bff; text-decoration: none;">🔙 Volver al Mapa</a>

    <table>
        <tr>
            <th>Placa</th>
            <th>Celda</th>
            <th>Propietario / Celular</th>
            <th>Recibido por</th>
            <th>Fecha Entrega</th>
            <th>Acción</th>
        </tr>
        {% for entrega in entregas %}
        <tr>
            <td><strong>{{ entrega.matricula }}</strong><br><span>{{ entrega.marca }}</span></td>
            <td><strong>{{ entrega.codigo_celda }}</strong></td>
            <td>{{ entrega.propietario or 'N/A' }}<br>📱 {{ entrega.celular or 'N/A' }}</td>
            <td>{{ entrega.recibe or 'N/A' }}</td>
            <td>{{ entrega.fecha_hora_entrega }}</td>
            <td>
                <form class="form-entrega" action="/marcar-entregado/{{ entrega.id_movimiento }}" method="POST">
                    <input type="text" name="entrega" placeholder="¿Quién lo retira?" required>
                    <button class="btn-entregar" type="submit">Dar Salida</button>
                </form>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="6">No hay vehículos en el parqueadero.</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

# ==========================================
# RUTAS CON PROTECCIÓN ANTI-ERRORES
# ==========================================
@app.route('/')
def mapa_parqueadero():
    try:
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
        return render_template_string(HTML_MAPA, celdas=celdas)
    except Exception as e:
        return f"<h1>⚠️ ERROR AL CARGAR EL MAPA</h1><h3 style='color:red;'>{str(e)}</h3><p><b>Solución:</b> Entra a <a href='/instalar'>este enlace</a> para reparar las tablas.</p><pre>{traceback.format_exc()}</pre>"

@app.route('/registro', methods=['GET', 'POST'])
def registrar_vehiculo():
    try:
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
            cur.execute("""
                INSERT INTO vehiculos (matricula, marca, color, propietario, celular) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (matricula) DO UPDATE SET 
                marca = EXCLUDED.marca, color = EXCLUDED.color, propietario = EXCLUDED.propietario, celular = EXCLUDED.celular;
            """, (matricula, marca, color, propietario, celular))
            
            cur.execute("""
                INSERT INTO movimientos (matricula, id_celda, fecha_hora_recepcion, fecha_hora_entrega, recibe)
                VALUES (%s, %s, %s, %s, %s);
            """, (matricula, id_celda, fecha_recepcion, fecha_entrega, recibe))
            
            cur.execute("UPDATE celdas SET estado = 'ocupada' WHERE id_celda = %s;", (id_celda,))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('mapa_parqueadero'))
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id_celda, codigo_celda, tipo FROM celdas WHERE estado = 'libre' ORDER BY id_celda ASC;")
        celdas_libres = cur.fetchall()
        cur.close()
        conn.close()
        return render_template_string(HTML_REGISTRO, celdas_libres=celdas_libres)
    except Exception as e:
        return f"<h1>⚠️ ERROR AL REGISTRAR</h1><p style='color:red;'>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

@app.route('/entregas-pendientes')
def listado_entregas():
    try:
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
        return render_template_string(HTML_ENTREGAS, entregas=entregas)
    except Exception as e:
        return f"<h1>⚠️ ERROR EN ENTREGAS</h1><p style='color:red;'>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

@app.route('/marcar-entregado/<int:id_movimiento>', methods=['POST'])
def marcar_entregado(id_movimiento):
    entrega = request.form.get('entrega', 'No especificado')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_celda FROM movimientos WHERE id_movimiento = %s;", (id_movimiento,))
    id_celda = cur.fetchone()[0]
    cur.execute("UPDATE celdas SET estado = 'libre' WHERE id_celda = %s;", (id_celda,))
    cur.execute("UPDATE movimientos SET estado_movimiento = 'devuelto', entrega = %s WHERE id_movimiento = %s;", (entrega, id_movimiento))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('listado_entregas'))

@app.route('/api/alertas')
def api_alertas():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT m.matricula, c.codigo_celda, m.fecha_hora_entrega
            FROM movimientos m JOIN celdas c ON m.id_celda = c.id_celda
            WHERE DATE(m.fecha_hora_entrega) <= CURRENT_DATE AND m.estado_movimiento = 'en_parqueadero';
        """)
        pendientes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"hay_entregas": len(pendientes) > 0, "cantidad": len(pendientes)})
    except:
        return jsonify({"hay_entregas": False})

# ==========================================
# CREADOR DIRECTO DE TABLAS (SIN CONSOLAS)
# ==========================================
@app.route('/instalar')
def instalar_tablas():
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
                matricula VARCHAR(10) PRIMARY KEY, marca VARCHAR(50), color VARCHAR(30),
                propietario VARCHAR(100), celular VARCHAR(20)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id_movimiento SERIAL PRIMARY KEY, matricula VARCHAR(10) REFERENCES vehiculos(matricula),
                id_celda INT REFERENCES celdas(id_celda), fecha_hora_recepcion TIMESTAMP NOT NULL,
                fecha_hora_entrega TIMESTAMP NOT NULL, estado_movimiento VARCHAR(20) DEFAULT 'en_parqueadero',
                recibe VARCHAR(50), entrega VARCHAR(50)
            );
        """)
        
        # Insertar 140 celdas
        cur.execute("SELECT COUNT(*) FROM celdas;")
        if cur.fetchone()[0] < 140:
            for i in range(1, 21):
                cur.execute("INSERT INTO celdas (codigo_celda, tipo) VALUES (%s, 'interna') ON CONFLICT DO NOTHING;", (f"INT-{i:02d}",))
            for i in range(1, 121):
                cur.execute("INSERT INTO celdas (codigo_celda, tipo) VALUES (%s, 'externa') ON CONFLICT DO NOTHING;", (f"EXT-{i:03d}",))
        
        conn.commit()
        cur.close()
        conn.close()
        return "<h1>✅ INSTALACIÓN PERFECTA</h1><p>Las tablas nuevas con las 140 celdas están listas.</p><a href='/' style='font-size:24px;'>👉 HAZ CLIC AQUÍ PARA IR AL MAPA</a>"
    except Exception as e:
        return f"<h1>❌ ERROR CREANDO TABLAS</h1><p style='color:red;'>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

@app.route('/reset-urgente-db')
def reset_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS movimientos CASCADE;")
    cur.execute("DROP TABLE IF EXISTS vehiculos CASCADE;")
    cur.execute("DROP TABLE IF EXISTS celdas CASCADE;")
    conn.commit()
    cur.close()
    conn.close()
    return "✅ Base de datos limpiada. Ahora entra a /instalar"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)