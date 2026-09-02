# Terceros

SENDA.V0 incorpora o utiliza componentes de terceros incluidos en `vendor/`, `tools/` o en el runtime privado de Windows:

- Python 3.12 (PSF License).
- openpyxl y et_xmlfile.
- XlsxWriter.
- rarfile.
- xlrd 2.0.2 (BSD), usado para leer Excel binario `.xls`.
- 7-Zip (LGPL-2.1-or-later con restricción unRAR aplicable a su código RAR), incluido por el workflow oficial de Windows para extracción de RAR.

El runtime Windows se obtiene de Python.org. La versión instalable no reemplaza el Python del sistema. Los avisos/licencias de cada proyecto deben conservarse en cualquier redistribución.
