# Continuar Perfect Trading Catalog System

## Proyecto oficial

La única raíz oficial de este proyecto es:

```text
C:\PERFECT_CATALOG
```

Abrir esa carpeta como proyecto local en Codex. No crear otro repositorio y no sustituir su arquitectura.

## Contexto importante

`C:\PERFECT_CATALOG` es el catálogo de gran escala que se viene construyendo aquí. Ya contiene trabajo real y verificado:

- FastAPI y PostgreSQL.
- Importador Odoo con dry-run, hashes, aprobación y apply auditado.
- Estados, revisión humana y permisos mínimos.
- Releases inmutables y publicación controlada.
- API de consulta y catálogo web local.
- Consola web protegida para operadores.
- Centro seguro de ingreso de XLSX/CSV/TSV/PDF/ZIP.
- Migraciones SQL y una suite amplia de pruebas.

Las otras rutas y `catalog_app.zip` pertenecen al prototipo anterior trabajado con Claude. Ese prototipo no es la arquitectura final. Solo aporta piezas funcionales que deben portarse selectivamente.

## Objetivo del siguiente bloque

Integrar en el repositorio existente, sin duplicar sistemas, estas capacidades del prototipo:

1. Parser de nombres y aplicaciones vehiculares de `name_parser.py`.
2. Lectura y detección flexible de columnas de `csv_reader.py`, sólo donde complemente el importador Odoo actual.
3. Generación de catálogos PDF de `pdf_generator.py`.
4. Generación de catálogos PowerPoint de `pptx_generator.py`.
5. Pruebas con datos sintéticos para conservar el comportamiento funcional.

## Reglas de integración

- Leer primero `C:\PERFECT_CATALOG\AGENTS.md`, `PROJECT.md` y `HANDOFF.md` completos.
- Revisar el estado Git y preservar cualquier cambio local existente.
- Usar el paquete actual `src/perfect_catalog`; no crear un segundo paquete `app`.
- No sustituir las migraciones SQL actuales por otro sistema de modelos o migraciones.
- No portar SQLite ni `catalog_app.db`.
- No copiar el upsert antiguo; el flujo actual de dry-run/aprobación/apply es la autoridad.
- No debilitar hashes, auditoría, revisión humana, releases o controles de seguridad existentes.
- No portar el matching ambiguo de imágenes. Cualquier asociación conflictiva requiere revisión humana.
- El parser debe generar sugerencias o enriquecimiento pendiente de revisión, nunca publicar automáticamente.
- Los generadores deben consumir snapshots/releases verificados o fixtures sintéticos, no consultar datos empresariales de forma improvisada.
- Mantener compatibilidad con Windows y rutas portables.
- No incluir secretos, contraseñas, `.env`, datos comerciales, imágenes ni exportaciones reales en Git.
- No implementar todavía InDesign completo, R2 ni una carga de 25.000 productos.

## Orden de trabajo recomendado

### 1. Auditoría antes de editar

- Ejecutar la suite actual y anotar el número de pruebas aprobadas.
- Identificar la forma exacta de los snapshots de productos publicados.
- Revisar dependencias y empaquetado en `pyproject.toml`.
- Comparar el lector actual con `csv_reader.py` antes de decidir qué funciones portar.

### 2. Portar el parser

- Crear un módulo coherente con `src/perfect_catalog`.
- Separar el parseo de cualquier operación de base de datos.
- Añadir fixtures sintéticos representativos de autopartes.
- Marcar procedencia y estado de revisión de los resultados cuando se integren al workflow.

### 3. Portar PDF y PPTX

- Mantener los motores desacoplados de FastAPI y PostgreSQL.
- Crear un adaptador desde el snapshot/release actual al formato esperado por los generadores.
- Conservar portada, agrupaciones, aplicaciones, OEM, branding, 1–3 columnas y plantillas existentes.
- Verificar que los bytes producidos sean PDF/PPTX válidos y que tengan páginas/diapositivas.

### 4. Complementar CSV/XLSX

- Reutilizar únicamente detección de aliases, codificaciones y mapping que aporte valor.
- No reemplazar el contrato Odoo actual ni relajar sus controles de identidad.
- Toda entrada continúa pasando por cuarentena, perfilado, dry-run y revisión.

### 5. Cierre del bloque

- Ejecutar toda la suite, no sólo las pruebas nuevas.
- Actualizar `HANDOFF.md` con creado, portado, probado y pendiente.
- Hacer commits pequeños y claros por capacidad.
- Dejar el árbol Git limpio.

## Material reutilizable preparado

Existe una copia de trabajo provisional en:

```text
C:\Users\Diseño2\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\outputs\catalog-v2
```

No debe copiarse completa sobre el proyecto. Solo sirve como referencia para los cuatro módulos portados y sus pruebas. La arquitectura, modelos, configuración, FastAPI y Alembic de esa carpeta provisional deben ignorarse porque `C:\PERFECT_CATALOG` ya tiene implementaciones más maduras.

## Encargo para Codex

Continúa el proyecto oficial en `C:\PERFECT_CATALOG`. Integra selectivamente el parser, el lector flexible y los generadores PDF/PPTX del prototipo, respetando la arquitectura, seguridad, importación auditada, releases y pruebas existentes. Antes de editar, presenta un diagnóstico breve de los puntos exactos de integración. Después implementa por fases, ejecuta toda la suite y devuelve estado preciso de creado, portado, probado y pendiente. No crees otro repositorio ni reemplaces componentes maduros del proyecto.
