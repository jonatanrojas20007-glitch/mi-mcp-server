import asyncio
from pathlib import Path
from fastmcp import Client

# Apunta directamente al archivo server.py en el mismo directorio
SERVER_PATH = Path(__file__).parent / "server.py"

async def main():
    async with Client(str(SERVER_PATH)) as client:
        print("--> Conectado al servidor MCP vía FastMCP Client\n")

        # 1. Listar herramientas
        tools = await client.list_tools()
        print("Herramientas registradas:")
        for t in tools:
            print(f" - {t.name}: {t.description}")
        print("-" * 50)

        # 2. Listar tablas
        tablas = await client.call_tool("listar_tablas")
        print(f"Tablas disponibles: {tablas}\n")

        # 3. Analizar estadísticas de la tabla 'ventas'
        estadisticas = await client.call_tool(
            "analizar_estadisticas_tabla",
            {"nombre_tabla": "ventas"}
        )
        print("Resumen estadístico:")
        print(estadisticas)
        print("-" * 50)

        # 4. Ejecutar consulta SQL
        query_sql = "SELECT producto, SUM(monto * unidades) as total FROM ventas GROUP BY producto"
        resultado_query = await client.call_tool(
            "ejecutar_consulta_solo_lectura",
            {"query": query_sql}
        )
        print("Resultado de la consulta SQL:")
        print(resultado_query)

if __name__ == "__main__":
    asyncio.run(main())