# SENDA.V0 0.4.2 · Escritorio Windows

SENDA.V0 0.4.2 abandona el navegador como interfaz de la aplicación instalada. La versión Windows usa una ventana de escritorio nativa (Tk/ttk), accede directamente a SQLite y al motor de importación Python, y no necesita Chrome, Edge, `localhost` ni conexión a Internet para trabajar una vez compilada/instalada.

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

## Instalar desde GitHub

El workflow publica automáticamente una **Release** con `SENDA.V0_0.4.2_WINDOWS_DESKTOP.zip`. Hay dos rutas:

1. **Release:** abrir **Releases → Latest**, descargar el ZIP, extraerlo y ejecutar `INSTALAR_SENDA_V0.bat`.
2. **Desde una copia del repositorio:** ejecutar `INSTALAR_DESDE_GITHUB.bat`; el script consulta la Release más reciente, descarga el paquete oficial y ejecuta el instalador.

En ambos casos la aplicación se instala en `%LOCALAPPDATA%\Programs\SENDA.V0` y los datos permanecen en `%LOCALAPPDATA%\SENDA.V0`.

## Compilar en GitHub

1. Subir el contenido de este repositorio a GitHub.
2. Abrir **Actions → Build SENDA.V0 Windows Desktop → Run workflow**.
3. El workflow ejecuta pruebas, construye `SENDA.V0.exe`, valida `--check`, publica el artefacto y actualiza la Release **v0.4.2**.

## Regla anti-duplicados

- SENDA calcula SHA-256 del conjunto de archivos seleccionados. Si el mismo corte ya terminó una importación, no lo vuelve a cargar.
- Cada movimiento tiene además una firma lógica independiente de `archivo_origen`; un archivo renombrado, otro ZIP/RAR o una nueva exportación con el mismo movimiento no lo duplica.
- La migración crea el índice de firmas sin borrar movimientos existentes.
- El resultado de importación separa **nuevos**, **duplicados evitados**, **omitidos por reglas** y **errores**.

## Compatibilidad de carga Desktop

La carga acepta por contenido real: **XLS, XLSX, CSV, JSON, TXT, ZIP y RAR**. XLS binario usa `xlrd` incluido en el build; XLSX usa `openpyxl`; el paquete Windows incorpora 7-Zip para RAR. ZIP/RAR pueden contener carpetas y ZIP anidados.

## Verificación local de código

```bash
python -m pytest -q
python -m app.desktop --check --data-dir <carpeta-temporal>
```

`--check` valida SQLite y las migraciones sin abrir interfaz ni iniciar servidor HTTP.


## SENDA.V0 0.4.2 Desktop

- Inicio agrega **TRÁMITES PENDIENTES** y conserva estadísticas dinámicas.
- Información SENDA muestra alarmas visibles **🔴 ROJA / 🟡 AMARILLA / 🟢 VERDE**.
- Gestión incorpora gráfico de **Trámites realizados por mes**.
- Gestión exporta **Base SENDA fusionable** en Excel o JSON con movimientos, expedientes, estados, fechas y auditoría.
- `CARGAR DATOS` reconoce una Base SENDA Excel/JSON exportada en otra computadora y fusiona cambios sin borrar la base local.
- Movimientos repetidos continúan deduplicándose por firma lógica.
- Tipografía aumentada aproximadamente 20% y acciones principales usan botones redondeados.
- Se mantiene **↻ ACTUALIZAR DESDE GITHUB** y la persistencia en `%LOCALAPPDATA%\SENDA.V0`.
- Importadores registrales: XLS, XLSX, CSV, JSON, TXT, ZIP y RAR.
