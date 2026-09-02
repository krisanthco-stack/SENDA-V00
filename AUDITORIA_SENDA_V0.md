# Auditoría SENDA.V0 0.4.0 Desktop

## Fallo histórico eliminado por arquitectura

Las versiones web instaladas abrían una interfaz mediante Chrome/Edge contra `127.0.0.1`. Esto producía errores recurrentes cuando la API, la UI o una importación larga interrumpían la conexión HTTP. SENDA.V0 0.4.0 Desktop elimina ese camino en la aplicación Windows.

La entrada Windows ahora es `SENDA.V0.exe` → `app.desktop` → `Repository/ImportEngine` → SQLite. No hay servidor HTTP, navegador ni `localhost` en el flujo de escritorio.

## Persistencia

Se conserva `app.config.default_data_dir()`, por lo que 0.4.0 usa el mismo `%LOCALAPPDATA%\SENDA.V0` que 0.3.0. Las migraciones de `Repository` son aditivas y no recrean la base.

## Workflow funcional recuperado

- Inicio // Información SENDA // Control // Gestión.
- Selección múltiple de folios en Información SENDA.
- Varios trámites simultáneos en Control.
- FINALIZAR se activa únicamente con trámite abierto.
- Finalizar mueve el expediente a Gestión sin borrar movimientos.
- Expedientes manuales y editables.
- Derechos subdivididos por folio.
- Movimientos 25/50/100 y orden antiguo → nuevo.
- Categorías Fincas / Hipotecas / Gravámenes / Segregaciones / Anotaciones / Históricos / Cerradas / Otros.
- Exportación JSON/CSV/XLSX.

## Regresiones automatizadas

La suite exige que `INICIAR_SENDA_V0.bat` no contenga `127.0.0.1`, Chrome, Edge, HTTP ni `app.launcher`. `app.desktop` no importa `app.server`, `webbrowser`, `requests` ni `urllib`.

La actualización no puede ejecutar `Remove-Item $DataRoot` y la desinstalación conserva datos salvo confirmación explícita `ELIMINAR`.
