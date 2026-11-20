# server_sysmon.py
import json
import psutil
from fastmcp import FastMCP

mcp = FastMCP("System-Monitor-MCP")


@mcp.tool()
def obtener_metricas_sistema() -> str:
    """Retorna el uso actual de CPU, memoria RAM y particiones principales."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    stats = {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_cores_logicos": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_usada_gb": round(mem.used / (1024 ** 3), 2),
        "ram_porcentaje": mem.percent,
        "disco_usado_porcentaje": disk.percent,
        "disco_libre_gb": round(disk.free / (1024 ** 3), 2)
    }
    return json.dumps(stats, indent=2)


@mcp.tool()
def listar_top_procesos_consumo(limite: int = 5) -> str:
    """Lista los N procesos que consumen más memoria RAM en la máquina."""
    procesos = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
        try:
            info = proc.info
            procesos.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Ordenar por uso de memoria descendente
    top_proc = sorted(procesos, key=lambda p: p['memory_percent'] or 0, reverse=True)[:limite]
    return json.dumps(top_proc, indent=2)


if __name__ == "__main__":
    mcp.run()