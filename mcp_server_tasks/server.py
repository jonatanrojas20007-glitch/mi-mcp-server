from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from fastmcp import FastMCP
from google import genai

mcp = FastMCP("Task-Manager-MCP")

DB_PATH: Path = Path(__file__).resolve().parent / "tasks.db"
PRIORIDADES_VALIDAS = ("baja", "media", "alta")
ESTADOS_VALIDOS = ("pendiente", "en_progreso", "completada")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def _ahora_iso() -> str:
    """Retorna la marca de tiempo UTC actual en formato ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _get_connection(db_path: Path | None = None):
    """Abre una conexión SQLite con row_factory como diccionario y la cierra al salir."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _candidatos_db() -> list[Path]:
    """Devuelve rutas candidatas para SQLite (TASKS_DB_PATH, carpeta local o temporal)."""
    env_path = os.getenv("TASKS_DB_PATH", "").strip()
    if env_path:
        return [Path(env_path).expanduser().resolve()]
    return [
        Path(__file__).resolve().parent / "tasks.db",
        Path(tempfile.gettempdir()) / "task_manager_mcp" / "tasks.db",
    ]


def _init_db() -> None:
    """Inicializa la tabla de tareas en la primera ruta escribible y carga ejemplos si está vacía."""
    global DB_PATH
    ultimo_error: Exception | None = None

    for candidato in _candidatos_db():
        try:
            candidato.parent.mkdir(parents=True, exist_ok=True)
            with _get_connection(candidato) as conn:
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
            DB_PATH = candidato
            return
        except (OSError, sqlite3.Error) as exc:
            ultimo_error = exc

    raise RuntimeError(f"No se pudo inicializar SQLite en ninguna ruta escribible: {ultimo_error}")


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


def _llamar_gemini(prompt: str, modelo: str = "") -> tuple[str | None, str | None, str | None]:
    """Ejecuta un prompt en Gemini usando GEMINI_API_KEY/GOOGLE_API_KEY.

    Retorna (modelo_usado, texto_respuesta, error_json).
    """
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return (
            None,
            None,
            _error_json(
                "Falta la variable de entorno GEMINI_API_KEY. "
                "Configúrala en Prefect Horizon (Environment Variables) o en tu terminal local."
            ),
        )

    modelo_objetivo = modelo.strip() or DEFAULT_GEMINI_MODEL
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=modelo_objetivo, contents=prompt)
        texto = (response.text or "").strip()
        if not texto:
            return modelo_objetivo, None, _error_json("Gemini no devolvió texto en la respuesta.")
        return modelo_objetivo, texto, None
    except Exception as exc:
        return modelo_objetivo, None, _error_json(f"Error al consultar Gemini ({modelo_objetivo}): {exc}")


@mcp.tool()
def consultar_gemini(prompt: str, modelo: str = "") -> str:
    """Envía una consulta directa a la API de Gemini usando la variable GEMINI_API_KEY del servidor."""
    prompt_limpio = prompt.strip()
    if not prompt_limpio:
        return _error_json("El prompt no puede estar vacío.")

    modelo_usado, texto, error = _llamar_gemini(prompt_limpio, modelo)
    if error:
        return error

    return json.dumps(
        {"modelo": modelo_usado, "respuesta": texto},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def planificar_tareas_con_gemini(objetivo: str = "", modelo: str = "") -> str:
    """Analiza las tareas pendientes o en progreso y genera un plan priorizado usando Gemini."""
    with _get_connection() as conn:
        activas = [
            dict(r)
            for r in conn.execute(
                "SELECT id, titulo, descripcion, prioridad, estado, etiqueta "
                "FROM tareas WHERE estado != 'completada' ORDER BY id ASC"
            ).fetchall()
        ]

    if not activas:
        return json.dumps(
            {"mensaje": "No hay tareas pendientes ni en progreso para planificar.", "tareas_analizadas": 0},
            ensure_ascii=False,
            indent=2,
        )

    contexto_objetivo = objetivo.strip() or "Maximizar avance resolviendo primero lo más urgente e importante."
    prompt = (
        "Eres un asistente de productividad técnico. "
        "Con base en estas tareas activas en formato JSON, genera un plan breve y accionable en español "
        "ordenando qué hacer primero, por qué, y el primer paso concreto para cada una.\n\n"
        f"Objetivo del usuario: {contexto_objetivo}\n\n"
        f"Tareas activas:\n{json.dumps(activas, ensure_ascii=False, indent=2)}"
    )

    modelo_usado, plan, error = _llamar_gemini(prompt, modelo)
    if error:
        return error

    return json.dumps(
        {
            "modelo": modelo_usado,
            "tareas_analizadas": len(activas),
            "plan": plan,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
