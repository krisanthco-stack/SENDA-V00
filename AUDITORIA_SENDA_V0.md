# Auditoría de regresión — SENDA.V0

## Fallos históricos cubiertos

1. **Ventana de servidor que se cierra sin explicación**
   - `INICIAR_SENDA_V0.bat` detecta Python, conserva el `ERRORLEVEL` y hace `pause` ante fallo.
   - `app.launcher` crea `logs/senda_v0.log`, espera `/api/health` y solo abre el navegador cuando el servidor responde.
   - Si el puerto 8765 está ocupado, el lanzador solicita automáticamente otro puerto libre.

2. **UI indica “servidor no disponible” por rutas faltantes**
   - Contratos automatizados cubren `/api/health`, `/api/dashboard`, `/api/movements`, `/api/imports`, `/api/cases` y exportaciones.

3. **XLS falso / XLS binario real**
   - La detección usa firma de contenido, no solo extensión.
   - `.xls` de texto heredado se trata como delimitado.
   - OLE/BIFF real se identifica como XLS y se prueba con fixture binario real.
   - Lectura BIFF intenta `xlrd` si está disponible y, en Windows, Microsoft Excel; también admite LibreOffice.

4. **Archivos grandes**
   - La carga HTTP escribe a disco en bloques de 1 MiB; no hay límite artificial de tamaño para importaciones.
   - CSV/TXT/JSON/XLSX se recorren incrementalmente; SQLite inserta en lotes.
   - El dashboard agrega en SQL y no materializa hasta 1.000.000 de filas en memoria.

5. **ZIP**
   - Reconocimiento por firma `PK`.
   - Carga por HTTP probada de extremo a extremo.
   - Múltiples archivos, subcarpetas y ZIP anidado.
   - Catálogos dentro del ZIP se cargan antes de movimientos.
   - Extracción en streaming y bloqueo de path traversal.

6. **RAR**
   - Reconocimiento de firmas RAR4/RAR5.
   - Integración con `rarfile` y extractores disponibles (7-Zip, WinRAR/unrar, tar/libarchive según el equipo).

7. **Catálogos tratados como movimientos**
   - `CATALOGO_COD_*` se almacena como metadatos.
   - `COD_OPERACION + CLASE_CODIGO` se resuelve (ej. `PE + 1 -> PE1 -> COMPRAVENTA`).
   - `STATUS` omite B/blanco y `CLASE_RESP=9` se omite.

8. **Período, distrito y alarmas**
   - T1 Ene–Mar, T2 Abr–Jun, T3 Jul–Sep, T4 Oct–Dic.
   - Filtros combinables: año, trimestre, mes, distrito y alarma.
   - Distritos: Puerto Viejo, La Virgen, Horquetas, Llanuras del Gaspar y Cureña.
   - Alarmas heredadas: rojo >= 90 días; amarillo > 60 días; verde <= 60 días.
   - La alarma se calcula sobre el último movimiento del folio dentro del conjunto filtrado.

9. **Actualización/desinstalación**
   - Código instalado en `%LOCALAPPDATA%\Programs\SENDA.V0`.
   - Datos separados en `%LOCALAPPDATA%\SENDA.V0`.
   - Actualizar reemplaza código sin tocar datos.
   - Desinstalar conserva datos por defecto; para borrarlos exige opción 2 y confirmación `ELIMINAR`.

## Alcance de pruebas

La suite automatizada cubre dominio, SQLite, importadores, ZIP, API, exportaciones, expedientes, UI horizontal de cuatro módulos y contratos de los scripts Windows. La entrega final debe volver a ejecutar esta suite desde una extracción limpia del ZIP.

## Regresión GitHub Pages · 0.1.1

- Se detectó que el repositorio no tenía `index.html` en la raíz y GitHub Pages mostraba documentación en vez de la aplicación.
- Se agregó entrada raíz que redirige a `ui/`, `.nojekyll` y una regresión automática.
- La vista publicada en GitHub Pages ya no intenta consultar `/api/*` inexistentes: muestra `Vista web` e indica que los datos se conectan mediante `INICIAR_SENDA_V0.bat`.
