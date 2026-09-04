import os
import pymysql
import pandas as pd
from sqlalchemy import create_engine
from langchain_ollama import ChatOllama

# Configuración de conexión a MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql-agente")
MYSQL_USER = os.getenv("MYSQL_USER", "agente_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "agente123")
MYSQL_DB = os.getenv("MYSQL_DB", "data_warehouse")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

def obtener_conexion_engine():
    connection = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        port=MYSQL_PORT
    )
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB};")
    connection.close()

    db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    return create_engine(db_url)

def ejecutar_pipeline_mysql():
    print("🚀 Iniciando Agente de Data Engineering (Pipeline SQL para MySQL)...\n")
    
    llm = ChatOllama(
        model="qwen2.5-coder",
        base_url="http://host.docker.internal:11434",
        temperature=0
    )

    engine = obtener_conexion_engine()

    # 1. Carga del CSV
    df_raw = pd.read_csv("datos_crudos.csv", on_bad_lines='skip')

    # 2. Pre-procesamiento seguro de fechas en Pandas (Soporta múltiples formatos sin lanzar error)
    if "fecha_compra" in df_raw.columns:
        df_raw["fecha_compra"] = pd.to_datetime(df_raw["fecha_compra"], format='mixed', errors='coerce').dt.strftime('%Y-%m-%d')

    # Carga a la tabla staging en MySQL
    df_raw.to_sql("stg_ventas_crudas", engine, if_exists="replace", index=False)
    print("📥 Datos crudos cargados y estandarizados en la tabla 'stg_ventas_crudas'.")

    # 3. Prompt simplificado donde fecha_compra ya viene limpia como YYYY-MM-DD
    prompt = """
    Eres un DBA e Ingeniero de Datos experto en MySQL 8.
    Escribe un script SQL en dialecto MySQL que realice la limpieza y transformación de la tabla 'stg_ventas_crudas' hacia la tabla final 'ventas_procesadas'.

    Instrucciones específicas en MySQL:
    1. Crea la tabla 'ventas_procesadas' si no existe (id INT, cliente VARCHAR(100), monto DECIMAL(10,2), fecha_compra DATE, categoria VARCHAR(50)).
    2. TRUNCATE TABLE ventas_procesadas.
    3. INSERT INTO ventas_procesadas (id, cliente, monto, fecha_compra, categoria) desde 'stg_ventas_crudas':
       - id
       - TRIM(cliente) AS cliente
       - CAST(COALESCE(REPLACE(REPLACE(REPLACE(monto, ',', '.'), '$', ''), 'N/A', '0'), '0') AS DECIMAL(10,2)) AS monto
       - CAST(fecha_compra AS DATE) AS fecha_compra
       - UPPER(TRIM(categoria)) AS categoria

    REGLA IMPORTANTE: Responde ÚNICAMENTE con las sentencias SQL dentro de un bloque markdown ```sql ... ```. No agregues explicaciones adicionales.
    """

    print("\n🤖 El agente está redactando el script SQL para MySQL...")
    respuesta = llm.invoke(prompt)
    
    codigo_respuesta = respuesta.content
    if "```sql" in codigo_respuesta:
        sql_limpio = codigo_respuesta.split("```sql")[1].split("```")[0].strip()
    elif "```" in codigo_respuesta:
        sql_limpio = codigo_respuesta.split("```")[1].split("```")[0].strip()
    else:
        sql_limpio = codigo_respuesta.strip()

    print("\n📝 Sentencias SQL generadas:\n")
    print(sql_limpio)
    print("\n⚙️ Ejecutando script SQL en el servidor MySQL...")

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        sentencias = [s.strip() for s in sql_limpio.split(";") if s.strip()]
        for stmt in sentencias:
            cursor.execute(stmt)
        raw_conn.commit()
    finally:
        raw_conn.close()

    print("\n✅ Transformación SQL ejecutada con éxito.")

    print("\n🔍 Registros procesados en la tabla 'ventas_procesadas' (MySQL):")
    df_resultado = pd.read_sql("SELECT * FROM ventas_procesadas", engine)
    print(df_resultado)

if __name__ == "__main__":
    ejecutar_pipeline_mysql()