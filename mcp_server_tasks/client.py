import asyncio
import json
from pathlib import Path
from fastmcp import Client

SERVER_PATH = Path(__file__).parent / "server.py"


async def main() -> None:
    async with Client(SERVER_PATH) as client:
        print("--> Conectado al servidor Task-Manager-MCP\n")

        tools = await client.list_tools()
        print("Herramientas expuestas:")
        for t in tools:
            print(f" - {t.name}: {t.description}")
        print("-" * 50)

        print("1) Listado inicial:")
        print(await client.call_tool("listar_tareas"))

        print("\n2) Creando tarea de prueba:")
        creada = await client.call_tool(
            "crear_tarea",
            {
                "titulo": "Probar con MCP Inspector",
                "descripcion": "Ejecutar npx @modelcontextprotocol/inspector python server.py",
                "prioridad": "alta",
                "etiqueta": "demo",
            },
        )
        print(creada)

        nueva_id = json.loads(creada.data)["tarea"]["id"]

        print(f"\n3) Marcando tarea {nueva_id} como completada:")
        print(await client.call_tool("actualizar_estado_tarea", {"tarea_id": nueva_id, "nuevo_estado": "completada"}))

        print("\n4) Resumen de productividad:")
        print(await client.call_tool("resumen_productividad"))

        print(f"\n5) Eliminando tarea de prueba {nueva_id}:")
        print(await client.call_tool("eliminar_tarea", {"tarea_id": nueva_id}))


if __name__ == "__main__":
    asyncio.run(main())
