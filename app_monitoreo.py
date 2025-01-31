import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
import time
import webbrowser
from datetime import datetime
import socket
from fpdf import FPDF
from PIL import Image
import io
from sklearn import model_selection, svm
import numpy as np
from sklearn.linear_model import LinearRegression

# Configuración de conexión a la base de datos
def conectar_base_datos():
    return mysql.connector.connect(
        host="localhost",  
        user="root",       
        password="1234",       
        database="monitoreo_db"
    )

# Guardar historial de acciones
def registrar_accion_historial(id_usuario, usuario, rol, accion, modulo, detalle, ip_origen):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    query = """
        INSERT INTO historial_usuarios (id_usuario, usuario, rol, accion, modulo, detalle, fecha_hora, ip_origen)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
    """
    cursor.execute(query, (id_usuario, usuario, rol, accion, modulo, detalle, ip_origen))
    conn.commit()
    conn.close()
def obtener_acciones_usuario(id_usuario):
    # Suponiendo que las acciones se almacenan en st.session_state
    acciones = st.session_state.get("acciones", [])
    return [accion for accion in acciones if accion["id_usuario"] == id_usuario]

# Función para autenticación de usuarios
def autenticar_usuario(usuario, contrasena):
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_usuario, usuario, nombre, rol FROM Usuarios WHERE usuario = %s AND contrasena = %s",
        (usuario, contrasena),
    )
    usuario = cursor.fetchone()
    conn.close()
    return usuario

# Página de inicio de sesión
# Inicializar el contador de intentos fallidos en la sesión
if "intentos_fallidos" not in st.session_state:
    st.session_state["intentos_fallidos"] = 0

# Página de inicio de sesión
if "usuario" not in st.session_state:
    st.title("🔐 Inicio de Sesión")

    # Bloquear acceso después de 3 intentos
    if st.session_state["intentos_fallidos"] >= 3:
        st.error("⛔ Has excedido el número máximo de intentos. Intenta más tarde.")
        st.stop()

    usuario = st.text_input("Usuario:")
    contrasena = st.text_input("Contraseña:", type="password")

    if st.button("Iniciar Sesión"):
        usuario_data = autenticar_usuario(usuario, contrasena)

        if usuario_data:
            st.session_state["usuario"] = usuario_data
            st.session_state["intentos_fallidos"] = 0  # Reiniciar intentos si es correcto
            st.success(f"Bienvenido, {usuario_data['nombre']}")

            # Registrar la acción de inicio de sesión en el historial
            registrar_accion_historial(
                id_usuario=usuario_data['id_usuario'],  
                usuario=usuario_data['nombre'],  
                rol=usuario_data['rol'],  
                accion="Iniciar Sesión",  
                modulo="Inicio de Sesión",  
                detalle=f"El usuario {usuario_data['nombre']} ha iniciado sesión.",  
                ip_origen=socket.gethostbyname(socket.gethostname())  
            )
            
            time.sleep(1)
            st.rerun()  # Recargar la página

        else:
            st.session_state["intentos_fallidos"] += 1
            intentos_restantes = 3 - st.session_state["intentos_fallidos"]
            st.error(f"Usuario o contraseña incorrectos. Intentos restantes: {intentos_restantes}")

    st.stop()

# Función para cargar luminarias
def cargar_luminarias():
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    
    # Actualizar el estado de las luminarias según la hora
    hora_actual = datetime.now().hour
    nuevo_estado = "encendido" if 18 <= hora_actual or hora_actual < 6 else "apagado"
    cursor.execute(f"UPDATE Luminarias SET estado = '{nuevo_estado}'")
    conn.commit()
    
    # Cargar luminarias con los datos actualizados
    cursor.execute("SELECT * FROM Luminarias")
    luminarias = cursor.fetchall()
    conn.close()
    return luminarias

# Función para agregar una luminaria
def agregar_luminaria(nombre_luminaria, ubicacion, estado, imagen_luminaria):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    sql = """
        INSERT INTO Luminarias (nombre_luminaria, ubicacion, estado, imagen_luminaria)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, (nombre_luminaria, ubicacion, estado, imagen_luminaria))
    conn.commit()
    conn.close()

# Función para eliminar una luminaria
def eliminar_luminaria(id_luminaria):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    sql = "DELETE FROM Luminarias WHERE id_luminaria = %s"
    cursor.execute(sql, (id_luminaria,))
    conn.commit()
    conn.close()

def cargar_sensores():
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Sensores")
    sensores = cursor.fetchall()
    conn.close()
    return sensores

# Función para agregar un sensor
def agregar_sensor(nombre_sensor, tipo, id_luminaria, imagen_sensor):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    sql = """
        INSERT INTO Sensores (nombre_sensor, tipo, id_luminaria, imagen_sensor)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, (nombre_sensor, tipo, id_luminaria, imagen_sensor))
    conn.commit()
    conn.close()

# Función para eliminar un sensor
def eliminar_sensor(id_sensor):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    sql = "DELETE FROM Sensores WHERE id_sensor = %s"
    cursor.execute(sql, (id_sensor,))
    conn.commit()
    conn.close()

def cargar_datos_sensor(sensor_id):
    conn = conectar_base_datos()
    query = """
        SELECT 
            ds.fecha_hora AS Hora,
            ds.valor AS Valor,
            s.nombre_sensor AS Sensor,
            a.nivel AS Nivel_Alerta
        FROM Datos_Sensores ds
        JOIN Sensores s ON ds.id_sensor = s.id_sensor
        LEFT JOIN Alertas a ON ds.id_dato = a.id_dato
        WHERE s.id_sensor = %s
        ORDER BY ds.fecha_hora ASC;
    """
    datos = pd.read_sql(query, conn, params=(sensor_id,))
    conn.close()
    return datos

# Definir los umbrales de alerta para cada tipo de sensor
UMBRALES = {
    "Sensor de Corriente (A)": {"min": 0, "max": 10},  
    "Sensor de Voltaje (V)": {"min": 210, "max": 240},
    "Sensor de Temperatura (°C)": {"min": -10, "max": 50},
    "Sensor de Humedad (%)": {"min": 20, "max": 80},
    "Sensor de Luz Ambiental (lx)": {"min": 100, "max": 2000}
}

# Función para obtener los datos recientes de sensores y generar alertas
def detectar_y_guardar_alertas():
    conexion = conectar_base_datos()
    cursor = conexion.cursor(dictionary=True)

    query = """
    SELECT ds.id_dato, ds.id_sensor, ds.fecha_hora, ds.valor, s.nombre_sensor, s.id_luminaria
    FROM datos_sensores ds
    INNER JOIN sensores s ON ds.id_sensor = s.id_sensor
    ORDER BY ds.fecha_hora DESC
    """
    cursor.execute(query)
    datos = cursor.fetchall()

    for dato in datos:
        nombre_sensor = dato["nombre_sensor"]
        valor = float(dato["valor"])
        id_dato = dato["id_dato"]

        if nombre_sensor in UMBRALES:
            umbral_min = UMBRALES[nombre_sensor]["min"]
            umbral_max = UMBRALES[nombre_sensor]["max"]

            if valor < umbral_min or valor > umbral_max:
                nivel = "alto" if valor > umbral_max * 1.2 or valor < umbral_min * 0.8 else "medio"
                
                cursor.execute("SELECT id_alerta FROM alertas WHERE id_dato = %s", (id_dato,))
                existe_alerta = cursor.fetchone()

                if not existe_alerta:
                    query_insert = """
                    INSERT INTO alertas (nivel, fecha_hora, id_dato, alerta)
                    VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(query_insert, (nivel, dato["fecha_hora"], id_dato, "no atendida"))
                    conexion.commit()

    conexion.close()

def cargar_alertas():
    conexion = conectar_base_datos()
    cursor = conexion.cursor(dictionary=True)

    query = """
    SELECT a.id_alerta, a.nivel, a.fecha_hora, ds.valor, s.nombre_sensor, s.id_luminaria, a.alerta
    FROM alertas a
    INNER JOIN datos_sensores ds ON a.id_dato = ds.id_dato
    INNER JOIN sensores s ON ds.id_sensor = s.id_sensor
    ORDER BY a.fecha_hora DESC
    """
    cursor.execute(query)
    alertas = cursor.fetchall()
    conexion.close()

    return pd.DataFrame(alertas)

def actualizar_estado_alerta(id_alerta, nuevo_estado):
    conexion = conectar_base_datos()
    cursor = conexion.cursor()
    query = "UPDATE alertas SET alerta = %s WHERE id_alerta = %s"
    cursor.execute(query, (nuevo_estado, id_alerta))
    conexion.commit()
    conexion.close()

# Agregar usuarios solo si es administrador
def agregar_usuario(usuario, nombre, apellido, fecha_nacimiento, genero, rol, contrasena):
    if rol not in ["Administrador", "Operador"]:
        st.error("El rol debe ser 'Administrador' u 'Operador'.")
        return
    conn = conectar_base_datos()
    cursor = conn.cursor()
    query = """
        INSERT INTO Usuarios (usuario, nombre, apellidos, fec_nac, genero, rol, contrasena)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (usuario, nombre, apellido, fecha_nacimiento, genero, rol, contrasena))
    conn.commit()
    conn.close()
    st.success(f"Usuario {nombre} agregado correctamente.")

# Obtener lista de usuarios desde la base de datos según el rol
def obtener_lista_usuarios_para_administrador():
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def obtener_lista_usuarios_para_operador():
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nombre, apellidos, genero, rol FROM Usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def obtener_lista_usuarios():
    """
    Recupera la lista de usuarios de la base de datos.
    Retorna una lista de diccionarios con la información de los usuarios.
    """
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_usuario, nombre, apellidos, rol FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def eliminar_usuario(id_usuario):
    """
    Elimina un usuario de la base de datos según su ID.
    :param id_usuario: ID del usuario a eliminar.
    """
    conn = conectar_base_datos()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
    conn.commit()
    conn.close()

# Función para obtener el historial completo
def mostrar_historial():
    conexion = conectar_base_datos()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM historial_usuarios ORDER BY fecha_hora DESC")
    historial = cursor.fetchall()
    conexion.close()
    return historial

# Función para obtener la lista de usuarios del historial
def obtener_usuarios():
    conexion = conectar_base_datos()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT usuario FROM historial_usuarios")
    usuarios = [fila["usuario"] for fila in cursor.fetchall()]
    conexion.close()
    return usuarios

# Función para obtener el historial filtrado
def obtener_historial_filtrado(usuario):
    conexion = conectar_base_datos()
    cursor = conexion.cursor(dictionary=True)
    query = """
        SELECT id_historial, usuario, rol, accion, modulo, detalle, fecha_hora, ip_origen
        FROM historial_usuarios
        WHERE usuario = %s
    """
    cursor.execute(query, (usuario,))
    historial = cursor.fetchall()
    conexion.close()
    return historial

# Función para generar el PDF
def generar_pdf(historial, usuario):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Historial del Sistema", ln=True, align="C")
    pdf.cell(200, 10, txt=f"Usuario: {usuario}", ln=True, align="C")

    pdf.ln(10)  # Espaciado
    for registro in historial:
        linea = (
            f"Fecha: {registro['fecha_hora']} | Acción: {registro['accion']} | "
            f"Módulo: {registro['modulo']} | Detalle: {registro['detalle']} | IP: {registro['ip_origen']}"
        )
        pdf.multi_cell(0, 10, txt=linea)

    nombre_archivo = f"historial_{usuario}.pdf"
    pdf.output(nombre_archivo)
    return nombre_archivo

# Sección de Predicciones
def cargar_datos_sensores_por_luminaria(id_luminaria):
    conn = conectar_base_datos()
    query = """
        SELECT ds.fecha_hora, ds.valor, s.nombre_sensor
        FROM datos_sensores ds
        INNER JOIN sensores s ON ds.id_sensor = s.id_sensor
        WHERE s.id_luminaria = %s
        ORDER BY ds.fecha_hora ASC
    """
    datos = pd.read_sql(query, conn, params=(id_luminaria,))
    conn.close()
    return datos

def entrenar_modelo(datos):
    if len(datos) < 2:
        st.warning("No hay suficientes datos para entrenar el modelo.")
        return None
    X = np.arange(len(datos)).reshape(-1, 1)
    y = datos["valor"].values
    modelo = LinearRegression()
    modelo.fit(X, y)
    return modelo

def predecir(modelo, datos):
    if modelo is None:
        return None
    X_pred = np.arange(len(datos), len(datos) + 5).reshape(-1, 1)
    return modelo.predict(X_pred)

def cargar_mantenimientos():
    conn = conectar_base_datos()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM mantenimientos ORDER BY fecha_programada DESC")
    mantenimientos = cursor.fetchall()
    conn.close()
    return mantenimientos
 
# Función para programar un mantenimiento
def programar_mantenimiento(id_luminaria, id_sensor, descripcion, fecha_programada, tipo_mantenimiento):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    query = """
        INSERT INTO mantenimientos (id_luminaria, id_sensor, fecha_programada, tipo_mantenimiento, estado, descripcion)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (id_luminaria, id_sensor, fecha_programada, tipo_mantenimiento, "pendiente", descripcion))
    conn.commit()
    conn.close()

# Función para actualizar el estado de un mantenimiento
def actualizar_estado_mantenimiento(id_mantenimiento, nuevo_estado, fecha_realizado=None):
    conn = conectar_base_datos()
    cursor = conn.cursor()
    if nuevo_estado == "completado" and fecha_realizado:
        query = """
            UPDATE mantenimientos
            SET estado = %s, fecha_realizado = %s
            WHERE id_mantenimiento = %s
        """
        cursor.execute(query, (nuevo_estado, fecha_realizado, id_mantenimiento))
    else:
        query = "UPDATE mantenimientos SET estado = %s WHERE id_mantenimiento = %s"
        cursor.execute(query, (nuevo_estado, id_mantenimiento))
    conn.commit()
    conn.close()

st.markdown("""
    <style>
        .stApp {
            background-image: url('https://png.pngtree.com/thumb_back/fh260/background/20201010/pngtree-abstract-system-technology-background-image_409296.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        .subtitle {
            text-align: center;
            color: #ffffff;
            font-size: 20px;
        }

        .stButton>button {
            background-color: #4a4a8a;
            color: white;
            border-radius: 8px;
            padding: 10px;
            font-size: 16px;
            transition: 0.3s;
        }

        .stButton>button:hover {
            background-color: #6a6ab8;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>💡 Sistema de Monitoreo Predictivo de Alumbrado Público</h1>", unsafe_allow_html=True)

# Configuración del sidebar
with st.sidebar:
    selected = option_menu(
        menu_title="Sistema de Monitoreo",
        options=[
            "Inicio",
            "Usuarios",
            "Luminarias",
            "Sensores",
            "Mantenimiento",
            "Predicciones",
            "Alertas",
            "Reportes",
            "Historial",
            "Exportar Historial",
            "Configuración",
            "Cerrar Sesión"
        ],
        icons=[
            "house",
            "person-circle",
            "lightbulb",
            "radar",
            "tools",
            "graph-up-arrow",
            "exclamation-triangle-fill",
            "bar-chart",
            "clock-history",
            "file-earmark-arrow-down",
            "gear",
            "box-arrow-right"
        ],
        menu_icon="cast",
        default_index=0,
    )

if selected == "Inicio":    
    st.title("🏠 Bienvenido al Sistema de Monitoreo")
    
    imagen_placeholder = st.empty()
    imagenes = ["monitoreo1.png", "monitoreo2.png", "monitoreo3.png", "monitoreo4.png"]
    
    while selected == "Inicio":
        for imagen in imagenes:
            imagen_placeholder.image(imagen, use_container_width=True)  # Cambio aquí
            time.sleep(2)  # Espera 2 segundo antes de cambiar

# Gestión de Usuarios
elif selected == "Usuarios":
    st.title("👥 Gestión de Usuarios")

    # Verificar que el usuario haya iniciado sesión
    if "usuario" not in st.session_state:
        st.error("Por favor, inicie sesión para acceder al sistema.")
        st.stop()

    # Verificar el rol del usuario
    rol_usuario = st.session_state["usuario"]["rol"].strip().lower()

    if rol_usuario == "administrador":
        # Mostrar todos los datos para el administrador
        st.subheader("📋 Lista Completa de Usuarios (Administrador)")
        usuarios = obtener_lista_usuarios_para_administrador()
        if usuarios:
            st.dataframe(usuarios)
        else:
            st.warning("⚠️ No hay usuarios registrados en la base de datos.")

        # Sección: Agregar Usuario
        st.subheader("➕👤 Agregar Usuario")
        with st.form("form_agregar_usuario"):
            usuario = st.text_input("Usuario:")
            nombre = st.text_input("Nombre:")
            apellido = st.text_input("Apellidos:")

            # Ajustar rango de fechas para `st.date_input`
            from datetime import date
            fecha_actual = date.today()
            rango_minimo = date(fecha_actual.year - 100, 1, 1)  # Usuarios nacidos hace máximo 100 años
            rango_maximo = fecha_actual  # No permitir fechas futuras

            fecha_nacimiento = st.date_input(
                "Fecha de Nacimiento:",
                min_value=rango_minimo,
                max_value=rango_maximo,
            )
            
            genero = st.radio("Género:", options=["Masculino", "Femenino", "Otro"])
            rol = st.selectbox("Rol:", options=["Administrador", "Operador"])
            contrasena = st.text_input("Contraseña:", type="password")
            confirmar_contrasena = st.text_input("Confirmar Contraseña:", type="password")

            if st.form_submit_button("Agregar Usuario"):
                # Validar que todos los campos estén llenos
                if not usuario or not nombre or not apellido or not fecha_nacimiento or not genero or not rol or not contrasena or not confirmar_contrasena:
                    st.error("Todos los campos son obligatorios. Por favor, complete el formulario.")
                elif contrasena != confirmar_contrasena:
                    st.error("Las contraseñas no coinciden.")
                else:
                    # Validar que el usuario sea mayor de 18 años
                    edad = fecha_actual.year - fecha_nacimiento.year - ((fecha_actual.month, fecha_actual.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
                    if edad < 18:
                        st.error("❌ El usuario debe ser mayor de 18 años.")
                    else:
                        # Agregar el usuario
                        agregar_usuario(usuario, nombre, apellido, fecha_nacimiento, genero, rol, contrasena)
                        registrar_accion_historial(
                            id_usuario=st.session_state["usuario"]["id_usuario"],
                            usuario=st.session_state["usuario"]["nombre"],
                            rol=st.session_state["usuario"]["rol"],
                            accion="Agregar Usuario",
                            modulo="Usuarios",
                            detalle=f"Se agregó un usuario con nombre {nombre} y rol {rol}.",
                            ip_origen=socket.gethostbyname(socket.gethostname())
                        )
                        st.success("✅ Usuario agregado correctamente.")

        # Sección: Eliminar Usuario
        st.subheader("🗑️ Eliminar Usuario")
        usuarios_eliminar = obtener_lista_usuarios_para_administrador()
        if usuarios_eliminar:
            usuario_seleccionado = st.selectbox(
                "Seleccione un usuario para eliminar:",
                options=[f"{usuario['id_usuario']} - {usuario['usuario']} - {usuario['nombre']} - {usuario['apellidos']} - {usuario['rol']}" for usuario in usuarios_eliminar]
            )
            if st.button("Eliminar"):
                id_usuario_a_eliminar = usuario_seleccionado.split(" - ")[0]
                eliminar_usuario(id_usuario_a_eliminar)
                registrar_accion_historial(
                    id_usuario=st.session_state["usuario"]["id_usuario"],
                    usuario=st.session_state["usuario"]["nombre"],
                    rol=st.session_state["usuario"]["rol"],
                    accion="Eliminar Usuario",
                    modulo="Usuarios",
                    detalle=f"Se eliminó el usuario con ID {id_usuario_a_eliminar}.",
                    ip_origen=socket.gethostbyname(socket.gethostname())
                )
                st.success("✅ Usuario eliminado correctamente.")
        else:
            st.info("No hay usuarios disponibles para eliminar.")

    elif rol_usuario == "operador":
        # Mostrar datos limitados para el operador
        st.subheader("📋 Lista Limitada de Usuarios (Operador)")
        usuarios = obtener_lista_usuarios_para_operador()
        if usuarios:
            st.dataframe(usuarios)
        else:
            st.warning("⚠️ No hay usuarios registrados en la base de datos.")
    else:
        st.error("❌ No tiene permisos para gestionar usuarios.")

# Historial de los usuarios
elif selected == "Historial":
    st.title("📜 Historial de los Usuarios")

    # Verificar que el usuario haya iniciado sesión
    if "usuario" not in st.session_state:
        st.error("Por favor, inicie sesión para acceder al sistema.")
        st.stop()

    # Verificar si el usuario tiene permisos de administrador
    if st.session_state["usuario"]["rol"].strip().lower() == "administrador":
        
        # Botón "Ver Historial"
        ver_historial = st.button("👀 Ver Historial")

        # Si se presiona "Ver Historial", mostrar el historial completo
        if ver_historial:
            st.markdown("### 📌 Historial Completo")
            historial = mostrar_historial()
            
            # Verificar si el historial contiene datos
            if historial and len(historial) > 0:
                st.dataframe(historial)
            else:
                st.warning("⚠️ No hay registros en el historial.")
    else:
        st.error("❌ No tiene permisos para visualizar el historial. Esta funcionalidad es solo para administradores.")

# Reportes
elif selected == "Reportes":
    st.title("📊 Generación de Reportes")

    # Verificar si hay sensores disponibles
    sensores = cargar_sensores()
    if sensores:
        # Selección del sensor
        sensor_seleccionado = st.selectbox(
            "Seleccione un sensor para generar el reporte:",
            options=[(sensor['id_sensor'], sensor['nombre_sensor'], sensor['id_luminaria']) for sensor in sensores],
            format_func=lambda x: f"ID: {x[0]} | {x[1]} | Luminaria: {x[2]}"
        )

        if sensor_seleccionado:
            sensor_id = sensor_seleccionado[0]
            st.write(f"Generando reporte para el sensor: {sensor_seleccionado[1]}")

            # Cargar datos del sensor seleccionado
            datos_sensor = cargar_datos_sensor(sensor_id)

            if not datos_sensor.empty:
                # Mostrar la tabla de datos
                st.dataframe(datos_sensor)

                # Graficar los datos
                st.markdown("### 📈 Gráfica de Valores del Sensor")
                plt.figure(figsize=(10, 5))

                # Graficar valores del sensor
                plt.plot(
                    datos_sensor["Hora"], datos_sensor["Valor"],
                    marker='o', linestyle='-', color='b', label="Valor del Sensor"
                )

                # Añadir alertas a la gráfica
                alertas = datos_sensor[~datos_sensor["Nivel_Alerta"].isnull()]
                plt.scatter(
                    alertas["Hora"], alertas["Valor"],
                    color='r', label="Alertas", zorder=5
                )

                plt.title(f"Valores registrados por el sensor {sensor_seleccionado[1]} con Alertas")
                plt.xlabel("Hora")
                plt.ylabel("Valor")
                plt.grid(True)
                plt.xticks(rotation=45)
                plt.legend()
                st.pyplot(plt)
            else:
                st.info(f"No hay datos disponibles para el sensor {sensor_seleccionado[1]}.")
    else:
        st.warning("No hay sensores disponibles en la base de datos.")

        
    # Cargar alertas desde la base de datos
    alertas = cargar_alertas()

    # Filtrar solo las alertas "no atendidas"
    alertas_no_atendidas = alertas[alertas["alerta"] == "no atendida"]

    if not alertas_no_atendidas.empty:
        st.markdown("### ⚠️ Alertas No Atendidas")
        for _, alerta in alertas_no_atendidas.iterrows():
            st.error(f"{alerta['alerta']} ({alerta['fecha_hora']})")
    else:
        st.info("No hay alertas no atendidas en el sistema.")

# Sección de alertas
elif selected == "Alertas":
    st.title("⚠️ Alertas del Sistema")

    # Detectar y guardar alertas antes de mostrar
    detectar_y_guardar_alertas()
    alertas = cargar_alertas()

    if not alertas.empty:
        for _, alerta in alertas.iterrows():
            with st.expander(f"Alerta ID: {alerta['id_alerta']}"):
                st.write(f"📅 Fecha y Hora: {alerta['fecha_hora']}")
                st.write(f"⚠️ Sensor: {alerta['nombre_sensor']} (Luminaria {alerta['id_luminaria']})")
                st.write(f"📊 Valor Registrado: {alerta['valor']}")
                st.write(f"🔥 Nivel de Severidad: {alerta['nivel'].capitalize()}")
                st.write(f"📝 Estado: {alerta['alerta'].capitalize()}")
                
                # Opciones de estado y normalización del valor actual
                opciones_estado = ["no atendida", "en revision", "resuelta"]
                estado_actual = alerta["alerta"].strip().lower()
                
                # Manejo de valores inesperados
                if estado_actual not in opciones_estado:
                    estado_actual = "no atendida"
                
                nuevo_estado = st.selectbox(
                    "📝 Cambiar estado:",
                    opciones_estado,
                    index=opciones_estado.index(estado_actual),
                    key=alerta["id_alerta"]
                )
                
                if st.button(f"Actualizar alerta {alerta['id_alerta']}"):
                    actualizar_estado_alerta(alerta['id_alerta'], nuevo_estado)
                    st.success("Estado actualizado correctamente.")
                    st.rerun()
    else:
        st.info("✅ No hay alertas activas en el sistema.")

#Luminarias
elif selected == "Luminarias":
    st.markdown("### 📍 Luminarias Disponibles")
    luminarias = cargar_luminarias()

    # Mostrar las luminarias en una cuadrícula
    cols = st.columns(2)  # Dos columnas por fila
    for i, lum in enumerate(luminarias):
        with cols[i % 2]:  # Alternar entre columnas
            # Decodificar la imagen de la base de datos
            if lum['imagen_luminaria']:
                imagen = Image.open(io.BytesIO(lum['imagen_luminaria']))
                st.image(imagen, caption=f"Luminaria {lum['id_luminaria']}", use_container_width=True)
            else:
                st.image("default_luminaria.jpg", caption=f"Luminaria {lum['id_luminaria']}", use_container_width=True)
            
            # Mostrar botón de detalles
            if st.button(f"Ver detalles de Luminaria {lum['id_luminaria']}"):
                st.markdown(f"#### Detalles de la Luminaria {lum['id_luminaria']}")
                st.write(f"Ubicación: {lum['ubicacion']}")
                st.write(f"Estado: {lum['estado']}")

#Sensores
elif selected == "Sensores":
    st.title("📡 Sensores Disponibles")
    sensores = cargar_sensores()
    # Mostrar las imágenes de los sensores en una cuadrícula
    cols = st.columns(5)  # Cinco columnas por fila
    for i, sensor in enumerate(sensores):
        with cols[i % 5]:  # Alternar entre columnas
            # Decodificar la imagen de la base de datos
            if sensor['imagen_sensor']:
                imagen = Image.open(io.BytesIO(sensor['imagen_sensor']))
                st.image(imagen, caption=f"Sensor {sensor['id_sensor']}", use_container_width=True)
            else:
                st.image("default_sensor.jpg", caption=f"Sensor {sensor['id_sensor']}", use_container_width=True)
            
            # Mostrar información del sensor
            st.markdown(f"**{sensor['nombre_sensor']}**")
            st.markdown(f"Tipo: {sensor['tipo']}")
            st.markdown(f"Luminaria: {sensor['id_luminaria']}")

# Exportar Historial
elif selected == "Exportar Historial":
    st.title("📥 Exportar Historial")

    # Verificar que el usuario haya iniciado sesión
    if "usuario" not in st.session_state:
        st.error("Por favor, inicie sesión para acceder al sistema.")
        st.stop()

    # Verificar si el usuario tiene permisos de administrador
    if st.session_state["usuario"]["rol"].strip().lower() == "administrador":
        # Obtener lista de usuarios desde la base de datos
        usuarios = obtener_usuarios()

        if usuarios:
            usuario_seleccionado = st.selectbox("Seleccione un usuario para exportar su historial:", usuarios)

            if st.button("Exportar Historial"):
                historial_filtrado = obtener_historial_filtrado(usuario_seleccionado)

                if historial_filtrado:
                    # Generar el archivo PDF
                    nombre_archivo = generar_pdf(historial_filtrado, usuario_seleccionado)

                    # Descargar el archivo PDF
                    with open(nombre_archivo, "rb") as file:
                        st.download_button(
                            label="📩 Descargar Historial en PDF",
                            data=file,
                            file_name=nombre_archivo,
                            mime="application/pdf",
                        )
                    st.success(f"✅ Historial del usuario '{usuario_seleccionado}' exportado correctamente.")
                else:
                    st.warning(f"No hay registros disponibles para el usuario '{usuario_seleccionado}'.")
        else:
            st.info("No hay usuarios registrados en el historial.")
    else:
        st.error("❌ No tiene permisos para exportar historial. Esta funcionalidad es solo para administradores.")

# Configuración de Dispositivos
elif selected == "Configuración":
    st.title("⚙️ Configuración de Dispositivos")
    
    # Verificar que el usuario haya iniciado sesión
    if "usuario" not in st.session_state:
        st.error("Por favor, inicie sesión para acceder al sistema.")
        st.stop()

    # Verificar si el usuario tiene permisos de administrador
    if st.session_state["usuario"]["rol"].strip().lower() == "administrador":
        # Agregar o eliminar luminarias
        st.subheader("Luminarias")
        with st.expander("Agregar Luminaria"):
            nombre_luminaria = st.text_input("Nombre de la luminaria:")
            ubicacion = st.text_input("Ubicación:")
            estado = st.selectbox("Estado inicial:", ["encendido", "apagado", "fallo"])
            imagen_luminaria = st.file_uploader("Cargar imagen de la luminaria:", type=["jpg", "png", "jpeg"])
        
            if st.button("Agregar Luminaria"):
                imagen_bytes = imagen_luminaria.read() if imagen_luminaria else None
                agregar_luminaria(nombre_luminaria, ubicacion, estado, imagen_bytes)
                # Registro de la acción en el historial
                registrar_accion_historial(
                    id_usuario=st.session_state["usuario"]["id_usuario"],
                    usuario=st.session_state["usuario"]["nombre"],
                    rol=st.session_state["usuario"]["rol"],
                    accion="Agregar Luminaria",
                    modulo="Luminarias",
                    detalle=(
                        f"Se agregó una luminaria con nombre '{nombre_luminaria}', ubicación '{ubicacion}'."
                    ),
                    ip_origen=socket.gethostbyname(socket.gethostname())  # IP del usuario
                )
                st.success("Luminaria agregada correctamente.")

        with st.expander("Eliminar Luminaria"):
            luminarias = cargar_luminarias()
            if luminarias:
                opciones = [f"{l['id_luminaria']} - {l['nombre_luminaria']}" for l in luminarias]
                seleccion = st.selectbox("Seleccione la luminaria a eliminar:", opciones)
                id_luminaria = seleccion.split(" - ")[0]
                nombre_luminaria = seleccion.split(" - ")[1]
            
                col1, col2 = st.columns(2)
                eliminar = col1.button("Eliminar")
                cancelar = col2.button("Cancelar")
        
                if eliminar:
                    eliminar_luminaria(id_luminaria)
                    registrar_accion_historial(
                        id_usuario=st.session_state["usuario"]["id_usuario"],
                        usuario=st.session_state["usuario"]["nombre"],
                        rol=st.session_state["usuario"]["rol"],
                        accion="Eliminar Luminaria",
                        modulo="Luminarias",
                        detalle=f"Se eliminó la luminaria con ID {id_luminaria} y nombre '{nombre_luminaria}'.",
                        ip_origen=socket.gethostbyname(socket.gethostname())  # IP del usuario
                    )
                    st.success(f"Luminaria '{nombre_luminaria}' eliminada correctamente.")
                elif cancelar:
                    st.info("La eliminación ha sido cancelada.")
            else:
                st.info("No hay luminarias registradas.")

        # Agregar o eliminar sensores
        st.subheader("Sensores")
        with st.expander("Agregar Sensor"):
            nombre_sensor = st.text_input("Nombre del sensor:")
            tipo = st.text_input("Tipo de sensor:")
            id_luminaria = st.selectbox("Luminaria asociada:", [l["id_luminaria"] for l in cargar_luminarias()])
            imagen_sensor = st.file_uploader("Cargar imagen del sensor:", type=["jpg", "png", "jpeg"])
        
            if st.button("Agregar Sensor"):
                imagen_bytes = imagen_sensor.read() if imagen_sensor else None
                agregar_sensor(nombre_sensor, tipo, id_luminaria, imagen_bytes)
                # Registro de la acción en el historial
                registrar_accion_historial(
                    id_usuario=st.session_state["usuario"]["id_usuario"],
                    usuario=st.session_state["usuario"]["nombre"],
                    rol=st.session_state["usuario"]["rol"],
                    accion="Agregar Sensor",
                    modulo="Sensores",
                    detalle=(
                        f"Se agregó un sensor con nombre '{nombre_sensor}', tipo '{tipo}', "
                        f"asociado a la luminaria con ID {id_luminaria}."
                    ),
                    ip_origen=socket.gethostbyname(socket.gethostname())  # IP del usuario
                )
                st.success("Sensor agregado correctamente.")
                
        with st.expander("Eliminar Sensor"):
            sensores = cargar_sensores()
            if sensores:
                opciones = [f"{s['id_sensor']} - {s['nombre_sensor']}" for s in sensores]
                seleccion = st.selectbox("Seleccione el sensor a eliminar:", opciones)
                id_sensor = seleccion.split(" - ")[0]
                nombre_sensor = seleccion.split(" - ")[1]
            
                col1, col2 = st.columns(2)
                eliminar = col1.button("Confirmar Eliminación")
                cancelar = col2.button("Cancelar")
        
                if eliminar:
                    eliminar_sensor(id_sensor)
                    registrar_accion_historial(
                        id_usuario=st.session_state["usuario"]["id_usuario"],
                        usuario=st.session_state["usuario"]["nombre"],
                        rol=st.session_state["usuario"]["rol"],
                        accion="Eliminar Sensor",
                        modulo="Sensores",
                        detalle=f"Se eliminó el sensor con ID {id_sensor} y nombre '{nombre_sensor}'.",
                        ip_origen=socket.gethostbyname(socket.gethostname())  # IP del usuario
                    )
                    st.success(f"Sensor '{nombre_sensor}' eliminado correctamente.")
                elif cancelar:
                    st.info("La eliminación ha sido cancelada.")
            else:
                st.info("No hay sensores registrados.")
    else:
        st.error("❌ No tiene permisos para acceder a la configuración de dispositivos. Esta funcionalidad es solo para administradores.")

        
#Predicciones
elif selected == "Predicciones":
    st.title("🤖 Predicción de Datos")
    st.subheader("Seleccionar Luminaria")
    id_luminaria = st.text_input("Ingrese ID de luminaria:")
    if id_luminaria:
        datos = cargar_datos_sensores_por_luminaria(id_luminaria)
        if datos.empty:
            st.info("No hay datos disponibles para esta luminaria.")
        else:
            st.write("Datos históricos:")
            st.write(datos[["fecha_hora", "valor", "nombre_sensor"]])
            if "modelo" not in st.session_state:
                st.session_state.modelo = None
            if st.button("Entrenar Modelo"):
                st.session_state.modelo = entrenar_modelo(datos)
                if st.session_state.modelo:
                    st.success("Modelo entrenado correctamente.")
            if st.button("Generar Predicción"):
                if st.session_state.modelo:
                    predicciones = predecir(st.session_state.modelo, datos)
                    if predicciones is not None:
                        st.write("Predicciones para los próximos 5 días:")
                        st.line_chart(predicciones)
                else:
                    st.warning("Entrene el modelo antes de generar la predicción.")

#Mantenimiento
elif selected == "Mantenimiento":
    st.title("🚧 Mantenimiento de Dispositivos")

    # Mostrar registros existentes
    st.subheader("Mantenimientos Programados")
    mantenimientos = cargar_mantenimientos()
    if mantenimientos:
        st.dataframe(mantenimientos)

        # Actualizar estado de un mantenimiento
        st.subheader("Actualizar Estado de Mantenimiento")
        id_mantenimiento = st.selectbox(
            "Seleccione un mantenimiento:",
            options=[m["id_mantenimiento"] for m in mantenimientos],
            format_func=lambda x: f" {x} - {next(m['descripcion'] for m in mantenimientos if m['id_mantenimiento'] == x)}"
        )
        nuevo_estado = st.selectbox("Estado:", ["pendiente", "en progreso", "completado"])
        fecha_realizado = None
        if nuevo_estado == "completado":
            fecha_realizado = st.date_input("Fecha de realización:")
        if st.button("Actualizar Estado"):
            actualizar_estado_mantenimiento(id_mantenimiento, nuevo_estado, fecha_realizado)
            st.success("Estado del mantenimiento actualizado correctamente.")
            st.rerun()

    else:
        st.info("No hay mantenimientos programados.")

    # Programar un nuevo mantenimiento
    st.subheader("Programar Mantenimiento")
    id_luminaria = st.text_input("ID de la luminaria:")
    id_sensor = st.text_input("ID del sensor (opcional):")
    descripcion = st.text_area("Descripción del mantenimiento:")
    fecha_programada = st.date_input("Fecha programada:")
    tipo_mantenimiento = st.selectbox("Tipo de mantenimiento:", ["preventivo", "correctivo", "predictivo"])
    if st.button("Programar Mantenimiento"):
        programar_mantenimiento(id_luminaria, id_sensor if id_sensor else None, descripcion, fecha_programada, tipo_mantenimiento)
        st.success("Mantenimiento programado correctamente.")
        st.rerun()

elif selected == "Cerrar Sesión":
    del st.session_state["usuario"]
    st.rerun()
