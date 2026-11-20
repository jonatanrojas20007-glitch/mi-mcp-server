# Servidores MCP en Python (FastMCP)

Colección de servidores **Model Context Protocol (MCP)** desarrollados con `FastMCP` para exponer herramientas locales por transporte `stdio`.

## Servidores incluidos

1. **`mcp_server_tasks/`** — `Task-Manager-MCP`
   - Gestor de tareas con persistencia local en SQLite (`tasks.db` generado automáticamente).
   - Herramientas: `crear_tarea`, `listar_tareas`, `actualizar_estado_tarea`, `eliminar_tarea`, `resumen_productividad`.
   - Incluye cliente de prueba en `mcp_server_tasks/client.py`.

2. **`mcp_server_db/`** — `Database-Analytics-Server`
   - Analítica de datos sobre SQLite con `SQLAlchemy` y `pandas`.
   - Herramientas: `listar_tablas`, `ejecutar_consulta_solo_lectura`, `analizar_estadisticas_tabla`.
   - Incluye cliente de prueba en `mcp_server_db/client.py`.

3. **`mcp_server_log/`** — `Log-Auditor-MCP`
   - Búsqueda de patrones con expresiones regulares en archivos de `./logs`.
   - Herramientas: `buscar_patron_log`.

4. **`mcp_server_sysmon/`** — `System-Monitor-MCP`
   - Monitor de recursos del sistema (CPU, RAM, disco y procesos) con `psutil`.
   - Herramientas: `obtener_metricas_sistema`, `listar_top_procesos_consumo`.

## Requisitos

```powershell
pip install -r requirements.txt
```

## Validación con MCP Inspector

Entra a la carpeta del servidor que quieras probar y ejecuta el Inspector oficial:

```powershell
cd mcp_server_tasks
npx @modelcontextprotocol/inspector python server.py
```

O ejecuta el cliente de prueba en Python:

```powershell
cd mcp_server_tasks
python client.py
```
