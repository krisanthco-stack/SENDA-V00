# SENDA.V0

Aplicación local para gestión registral de Sarapiquí, diseñada con interfaz horizontal compacta y cuatro módulos principales: **Inicio, Control, Expedientes y Configuración**.

## Formatos de importación

SENDA.V0 acepta **XLS, XLSX, CSV, JSON, TXT, ZIP y RAR**. ZIP puede contener carpetas, múltiples fuentes y ZIP anidados; los catálogos `CATALOGO_COD_*` se cargan primero como metadatos. Los archivos se reciben y procesan por streaming/lotes para evitar un límite artificial de tamaño impuesto por la aplicación.

## Períodos y filtros

- T1: enero–marzo
- T2: abril–junio
- T3: julio–septiembre
- T4: octubre–diciembre
- Filtros: año, trimestre, mes, distrito y alarma.
- Alarmas heredadas: rojo = 90 días o más sin movimiento; amarillo = más de 60 días; verde = hasta 60 días.

Distritos: Puerto Viejo, La Virgen, Horquetas, Llanuras del Gaspar y Cureña.

## Windows

1. Extraiga el ZIP completo.
2. Ejecute `INSTALAR_SENDA_V0.bat`.
3. Abra SENDA.V0 desde el acceso directo o `INICIAR_SENDA_V0.bat`.
4. Para una versión nueva, ejecute `ACTUALIZAR_SENDA_V0.bat` desde el paquete nuevo. Los datos se conservan.
5. Para retirar el programa, ejecute `DESINSTALAR_SENDA_V0.bat`; la opción predeterminada conserva los datos.

Los datos se guardan fuera del código en `%LOCALAPPDATA%\SENDA.V0`.
