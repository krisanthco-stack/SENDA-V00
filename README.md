# SENDA.V0 0.4.0 · Escritorio Windows

SENDA.V0 0.4.0 abandona el navegador como interfaz de la aplicación instalada. La versión Windows usa una ventana de escritorio nativa (Tk/ttk), accede directamente a SQLite y al motor de importación Python, y no necesita Chrome, Edge, `localhost` ni conexión a Internet para trabajar una vez compilada/instalada.

## Estructura funcional

**INICIO // INFORMACIÓN SENDA // CONTROL // GESTIÓN**

- **Inicio:** carga de XLS/XLSX, CSV, JSON, TXT, ZIP y RAR; estadísticas; contadores; exportación JSON/CSV/Excel.
- **Información SENDA:** folios/fincas/planos, movimientos, derechos, filtros por año/trimestre/mes/distrito/alarma, paginación 25/50/100, selección múltiple hacia Control y creación manual de expedientes.
- **Control:** varios trámites simultáneos, expediente editable, movimientos por categoría y botón **FINALIZAR** habilitado únicamente al abrir un trámite.
- **Gestión:** trámites finalizados, consulta de movimientos, edición administrativa y retorno auditado a Información SENDA.

## Movimientos

SENDA agrupa los movimientos en: Fincas, Hipotecas, Gravámenes, Segregaciones, Anotaciones, Históricos, Cerradas y Otros. Todos quedan ligados a folio/finca o plano; los derechos se muestran como subdivisiones y los movimientos se ordenan por defecto del más antiguo al más reciente.

## Datos y actualizaciones

Los datos se guardan fuera de la aplicación:

`%LOCALAPPDATA%\SENDA.V0\`

La base principal está en:

`%LOCALAPPDATA%\SENDA.V0\database\senda_v0.sqlite`

Actualizar reemplaza únicamente archivos de programa en `%LOCALAPPDATA%\Programs\SENDA.V0`. El script de actualización no contiene ninguna operación de borrado sobre la carpeta de datos. Desinstalar conserva los datos por defecto.

## Aplicación Windows independiente

El repositorio incluye `.github/workflows/build-windows-desktop.yml`. Ese workflow se ejecuta en `windows-latest`, prueba el proyecto y crea una distribución PyInstaller con:

- `SENDA.V0.exe` (ventana propia de Windows);
- runtime Python integrado por PyInstaller;
- Tk/ttk integrado;
- motores XLS/XLSX/Excel;
- 7-Zip incluido para RAR;
- scripts Instalar / Actualizar / Desinstalar.

El usuario final no necesita Python, Chrome ni Edge.

## Compilar en GitHub

1. Subir el contenido de este repositorio a GitHub.
2. Abrir **Actions → Build SENDA.V0 Windows Desktop → Run workflow**.
3. Descargar el artefacto **SENDA.V0-0.4.0-Windows-Desktop**.
4. Extraer `SENDA.V0_0.4.0_WINDOWS_DESKTOP.zip` y ejecutar `INSTALAR_SENDA_V0.bat`.

## Verificación local de código

```bash
python -m pytest -q
python -m app.desktop --check --data-dir <carpeta-temporal>
```

`--check` valida SQLite y las migraciones sin abrir interfaz ni iniciar servidor HTTP.
