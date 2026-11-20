# server_logs.py
import json
import re
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("Log-Auditor-MCP")

# Sandbox: solo permite examinar archivos en un directorio controlado
BASE_LOG_DIR = Path("./logs").resolve()
BASE_LOG_DIR.mkdir(exist_ok=True)

# Creamos un archivo de log de ejemplo si no existe
sample_log = BASE_LOG_DIR / "app.log"
if not sample_log.exists():
    sample_log.write_text(
        "2026-10-30 08:00:01 INFO Service started on port 8080\n"
        "2026-10-30 08:15:22 ERROR Database connection timeout on pool #3\n"
        "2026-10-30 08:20:10 WARN High latency detected in API gateway: 1200ms\n"
        "2026-10-30 08:45:00 ERROR Out of memory in worker worker-7\n"
    )


@mcp.tool()
def buscar_patron_log(archivo: str, patron_regex: str, max_coincidencias: int = 10) -> str:
    """
    Busca patrones de error o advertencia en un log específico dentro de la carpeta segura.
    Retorna las líneas que cumplen la expresión regular.
    """
    ruta_archivo = (BASE_LOG_DIR / archivo).resolve()

    # Prevenir Path Traversal (seguridad)
    if not str(ruta_archivo).startswith(str(BASE_LOG_DIR)):
        return json.dumps({"error": "Acceso denegado fuera de la carpeta de logs."})

    if not ruta_archivo.is_file():
        return json.dumps({"error": f"El archivo '{archivo}' no existe."})

    coincidencias = []
    regex = re.compile(patron_regex, re.IGNORECASE)

    with open(ruta_archivo, "r", encoding="utf-8", errors="ignore") as f:
        for num_linea, linea in enumerate(f, start=1):
            if regex.search(linea):
                coincidencias.append({"linea": num_linea, "contenido": linea.strip()})
                if len(coincidencias) >= max_coincidencias:
                    break

    return json.dumps({"total_encontrados": len(coincidencias), "resultados": coincidencias}, indent=2)


if __name__ == "__main__":
    mcp.run()