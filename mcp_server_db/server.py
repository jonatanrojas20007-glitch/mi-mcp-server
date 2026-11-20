import json
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from fastmcp import FastMCP

# Instanciar el servidor MCP
mcp = FastMCP("Database-Analytics-Server")

# Configurar motor de base de datos (ejemplo con SQLite local)
# Para Postgres: "postgresql+psycopg2://usuario:password@localhost:5432/mibase"
DB_URL = "sqlite:///analytics_demo.db"
engine = create_engine(DB_URL)


def setup_demo_data():
    """Genera datos de prueba si la base de datos está vacía."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY,
                producto TEXT,
                monto REAL,
                unidades INTEGER,
                region TEXT
            )
        """))
        # Insertar registros iniciales si no existen
        result = conn.execute(text("SELECT COUNT(*) FROM ventas")).scalar()
        if result == 0:
            conn.execute(text("""
                INSERT INTO ventas (producto, monto, unidades, region) VALUES
                ('Teclado Mecanico', 120.50, 4, 'Norte'),
                ('Monitor 4K', 450.00, 2, 'Centro'),
                ('Raton Inalambrico', 35.00, 10, 'Norte'),
                ('Laptop Stand', 45.00, 6, 'Sur'),
                ('Cable USB-C', 15.00, 25, 'Centro')
            """))
            conn.commit()


setup_demo_data()


@mcp.tool()
def listar_tablas() -> list[str]:
    """Retorna los nombres de todas las tablas presentes en la base de datos."""
    inspector = inspect(engine)
    return inspector.get_table_names()


@mcp.tool()
def ejecutar_consulta_solo_lectura(query: str) -> str:
    """
    Ejecuta una consulta SQL SELECT para extraer datos puntuales.
    Rechaza operaciones destructivas (DROP, INSERT, UPDATE, DELETE).
    """
    sanitized = query.strip().lower()
    if not sanitized.startswith("select"):
        return json.dumps({"error": "Solo se permiten consultas SELECT de lectura."})

    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
    return df.to_json(orient="records")


@mcp.tool()
def analizar_estadisticas_tabla(nombre_tabla: str) -> str:
    """
    Genera un perfil estadístico descriptivo (conteo, media, min, max, nulos)
    de una tabla para que un modelo o analista evalúe su comportamiento.
    """
    inspector = inspect(engine)
    if nombre_tabla not in inspector.get_table_names():
        return json.dumps({"error": f"La tabla '{nombre_tabla}' no existe."})

    df = pd.read_sql_table(nombre_tabla, con=engine)

    resumen = {
        "total_filas": int(len(df)),
        "columnas": list(df.columns),
        "valores_nulos_por_columna": df.isnull().sum().to_dict(),
        "resumen_numerico": df.describe().to_dict()
    }
    return json.dumps(resumen, indent=2)


if __name__ == "__main__":
    # Corre usando transporte stdio (estándar para integraciones locales)
    mcp.run()