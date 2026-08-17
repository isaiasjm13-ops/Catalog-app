# Odoo Profiler v0.1

Perfilador local y de solo lectura para exportaciones `.xlsx`, `.csv` y `.tsv` de Odoo.

No necesita paquetes de terceros, no usa PostgreSQL y no modifica el archivo analizado.

## Integración

Copie la carpeta `tools/` en la raíz de `C:\PERFECT_CATALOG`.

## Uso

Desde la raíz del proyecto:

```powershell
py -3.14 -m tools.odoo_profiler "data\imports\EMPAQUE CABEZOTE.xlsx"
```

Los reportes JSON y Markdown se guardan en `data/exports/profiles/`.

Para indicar otra carpeta:

```powershell
py -3.14 -m tools.odoo_profiler "archivo.xlsx" --output-dir "ruta\de\salida"
```

## Pruebas

```powershell
py -3.14 -m unittest discover -s tests -v
```

Las pruebas crean únicamente archivos sintéticos dentro de una carpeta temporal.
