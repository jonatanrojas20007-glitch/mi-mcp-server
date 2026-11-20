from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from fastmcp import FastMCP

mcp = FastMCP("Task-Manager-MCP")

DB_PATH = Path(__file__).resolve().parent / "tasks.db"
PRIORIDADES_VALIDAS = ("baja", "media", "alta")
ESTADOS_VALIDOS = ("pendiente", "en_progreso", "completada")


def _ahora_iso() -> str:
    """Retorna la marca de tiempo UTC actual en formato ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _get_connection():
    """Abre una conexión SQLite con row_factory como diccionario y la cierra al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db() -> None:
    """Inicializa la tabla de tareas y carga ejemplos si está vacía."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                prioridad TEXT NOT NULL DEFAULT 'media',
                estado TEXT NOT NULL DEFAULT 'pendiente',
                etiqueta TEXT NOT NULL DEFAULT 'general',
                creada_en TEXT NOT NULL,
                completada_en TEXT
            )
        """)
        total = conn.execute("SELECT COUNT(*) FROM tareas").fetchone()[0]
        if total == 0:
            ahora = _ahora_iso()
            conn.executemany(
                """
                INSERT INTO tareas (titulo, descripcion, prioridad, estado, etiqueta, creada_en)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("Configurar servidor MCP", "Validar herramientas con MCP Inspector", "alta", "en_progreso", "mcp", ahora),
                    ("Documentar endpoints", "Agregar ejemplos de uso en el repositorio", "media", "pendiente", "docs", ahora),
                    ("Revisar logs de prueba", "Verificar formato de salida JSON", "baja", "completada", "qa", ahora),
                ],
            )


def _error_json(mensaje: str) -> str:
    return json.dumps({"error": mensaje}, ensure_ascii=False, indent=2)


_init_db()


@mcp.tool()
def crear_tarea(
    titulo: str,
    descripcion: str = "",
    prioridad: str = "media",
    etiqueta: str = "general",
) -> str:
    """Crea una nueva tarea con prioridad ('baja', 'media', 'alta') y etiqueta."""
    titulo_limpio = titulo.strip()
    if not titulo_limpio:
        return _error_json("El título de la tarea no puede estar vacío.")

    prioridad_norm = prioridad.strip().lower()
    if prioridad_norm not in PRIORIDADES_VALIDAS:
        return _error_json(f"Prioridad inválida '{prioridad}'. Usa: {', '.join(PRIORIDADES_VALIDAS)}.")

    etiqueta_norm = etiqueta.strip().lower() or "general"
    ahora = _ahora_iso()

    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tareas (titulo, descripcion, prioridad, estado, etiqueta, creada_en)
            VALUES (?, ?, ?, 'pendiente', ?, ?)
            """,
            (titulo_limpio, descripcion.strip(), prioridad_norm, etiqueta_norm, ahora),
        )
        tarea = conn.execute("SELECT * FROM tareas WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return json.dumps({"mensaje": "Tarea creada", "tarea": dict(tarea)}, ensure_ascii=False, indent=2)


@mcp.tool()
def listar_tareas(
    estado: str = "todas",
    prioridad: str = "todas",
    etiqueta: str = "",
) -> str:
    """Lista las tareas registradas filtrando opcionalmente por estado, prioridad o etiqueta."""
    estado_norm = estado.strip().lower()
    prioridad_norm = prioridad.strip().lower()
    etiqueta_norm = etiqueta.strip().lower()

    if estado_norm != "todas" and estado_norm not in ESTADOS_VALIDOS:
        return _error_json(f"Estado inválido '{estado}'. Usa 'todas' o: {', '.join(ESTADOS_VALIDOS)}.")
    if prioridad_norm != "todas" and prioridad_norm not in PRIORIDADES_VALIDAS:
        return _error_json(f"Prioridad inválida '{prioridad}'. Usa 'todas' o: {', '.join(PRIORIDADES_VALIDAS)}.")

    condiciones = []
    params: list[str] = []

    if estado_norm != "todas":
        condiciones.append("estado = ?")
        params.append(estado_norm)
    if prioridad_norm != "todas":
        condiciones.append("prioridad = ?")
        params.append(prioridad_norm)
    if etiqueta_norm:
        condiciones.append("etiqueta = ?")
        params.append(etiqueta_norm)

    where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    query = f"SELECT * FROM tareas {where_sql} ORDER BY id DESC"

    with _get_connection() as conn:
        filas = [dict(r) for r in conn.execute(query, params).fetchall()]

    return json.dumps({"total": len(filas), "tareas": filas}, ensure_ascii=False, indent=2)


@mcp.tool()
def actualizar_estado_tarea(tarea_id: int, nuevo_estado: str) -> str:
    """Actualiza el estado de una tarea existente ('pendiente', 'en_progreso', 'completada')."""
    estado_norm = nuevo_estado.strip().lower()
    if estado_norm not in ESTADOS_VALIDOS:
        return _error_json(f"Estado inválido '{nuevo_estado}'. Usa: {', '.join(ESTADOS_VALIDOS)}.")

    completada_en = _ahora_iso() if estado_norm == "completada" else None

    with _get_connection() as conn:
        cursor = conn.execute(
            "UPDATE tareas SET estado = ?, completada_en = ? WHERE id = ?",
            (estado_norm, completada_en, tarea_id),
        )
        if cursor.rowcount == 0:
            return _error_json(f"No existe ninguna tarea con id={tarea_id}.")
        tarea = conn.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()

    return json.dumps({"mensaje": "Estado actualizado", "tarea": dict(tarea)}, ensure_ascii=False, indent=2)


@mcp.tool()
def eliminar_tarea(tarea_id: int) -> str:
    """Elimina permanentemente una tarea por su ID."""
    with _get_connection() as conn:
        cursor = conn.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
        if cursor.rowcount == 0:
            return _error_json(f"No existe ninguna tarea con id={tarea_id}.")

    return json.dumps({"mensaje": f"Tarea {tarea_id} eliminada correctamente."}, ensure_ascii=False, indent=2)


@mcp.tool()
def resumen_productividad() -> str:
    """Devuelve métricas agregadas de tareas por estado, prioridad pendiente y etiquetas."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tareas").fetchone()[0]
        por_estado = {
            row["estado"]: row["cantidad"]
            for row in conn.execute("SELECT estado, COUNT(*) AS cantidad FROM tareas GROUP BY estado")
        }
        pendientes_por_prioridad = {
            row["prioridad"]: row["cantidad"]
            for row in conn.execute(
                "SELECT prioridad, COUNT(*) AS cantidad FROM tareas WHERE estado != 'completada' GROUP BY prioridad"
            )
        }
        por_etiqueta = {
            row["etiqueta"]: row["cantidad"]
            for row in conn.execute("SELECT etiqueta, COUNT(*) AS cantidad FROM tareas GROUP BY etiqueta")
        }

    completadas = por_estado.get("completada", 0)
    porcentaje_completado = round((completadas / total) * 100, 1) if total > 0 else 0.0

    return json.dumps(
        {
            "total_tareas": total,
            "porcentaje_completado": porcentaje_completado,
            "por_estado": por_estado,
            "activas_por_prioridad": pendientes_por_prioridad,
            "por_etiqueta": por_etiqueta,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
