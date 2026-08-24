# HANDOFF.md - Estado de Traspasos Entre Sesiones

## Sesión Actual: Publicación controlada de releases (2026-08-24)

### Resultado de esta sesión

- Auditoría provisional documentada en `docs/STATUS_AUDIT_V2_2.md`.
- Bloqueo exacto: no se recibió `Manual_Desde_Cero_Perfect_Trading_Natsuki_v2.2.pdf`; solo llegó
  el texto del encargo. La conformidad literal con el manual no puede cerrarse hasta adjuntarlo.
- API FastAPI v1.1 de solo lectura implementada sin retirar el visor existente.
- El origen predeterminado es el último `catalog_release` publicado de una marca; búsqueda,
  categorías y detalle permanecen encerrados en ese release.
- Las URLs y respuestas publicadas usan UUID estable de variante o template. Los IDs
  `source-row:*` quedan limitados y rotulados como modo piloto XLSX explícito.
- Cada snapshot valida schema, identidad y hash canónico; el hash agregado valida marca, versión,
  orden e inventario completo de items antes de servir cualquier consulta.
- Workflow `build-release` / `inspect-release` / `publish-release` / `archive-release` implementado
  con actor, motivo, fingerprint/checksum exactos, transacciones serializables e idempotencia.
- La construcción exige plan aplicado, productos activos y una referencia interna primaria
  aprobada por identidad; aplicar datos nunca activa ni publica automáticamente.
- `catalog-release-v2` compromete criptográficamente también la definición y selección del release.
- La migración forward-only `0005` fue aplicada: triggers protegen releases, items y auditoría como
  append-only; solo permiten `draft → published → archived` y permisos mínimos por columna.
- `perfect-catalog-api` arranca el origen publicado por defecto. `INICIAR-SERVER.cmd` conserva el
  piloto local al pasar explícitamente `--source-dir data\imports`.
- Empaquetado corregido: `tools.odoo_profiler` funciona fuera de la raíz del repositorio.
- `.env.example` corregido para no presentar SQLite como base de desarrollo.
- Prueba de humo real: XLSX maestro de 893 filas, API devuelve catálogo y fichas correctamente.
- Contrato/importador v0.2: ya no exige 893 filas ni 13 columnas en orden exacto; acepta
  reordenamiento, conserva columnas nuevas y reporta opcionales ausentes, con límite de piloto.
- Segunda muestra real verificada: 237 filas y solo 2 columnas críticas, sin inventar opcionales.
- Workflow `approve-plan` / `apply-plan` implementado con actor, motivo y fingerprint obligatorios.
- El apply recalcula hashes, verifica el archivo, bloquea el plan y usa una transacción serializable;
  un segundo intento sobre un plan aplicado responde `already_applied` sin repetir escrituras.
- Alcance seguro actual: altas, snapshots completos, `no_change` y medios marcados pendientes. Las
  operaciones `update`, `blocked` y `conflict` se rechazan antes de escribir.
- `0003` fue aplicada en `perfect_catalog_dev`; flexibiliza el conteo opcional de variantes y limita
  por columna las transiciones permitidas al rol de aplicación.
- `0004` fue creada y aplicada forward-only para corregir drift de lectura con mínimo privilegio:
  `perfect_catalog_app` recibe SELECT solo en las 18 tablas que consume actualmente.
- Integración real como `perfect_catalog_app`: aprobación, alta, snapshot con -2/0, auditoría,
  reintento `already_applied`, permisos y rollback transaccional verificados.
- Integración del read model como `perfect_catalog_app`: selección, búsqueda, categorías, ficha por
  UUID y detección de manipulación, todo con datos sintéticos y rollback.
- Integración completa como rol real: apply sintético, activación/revisión sintética, build,
  checksum erróneo, publicación, lectura UUID, archivo, reintentos e inmutabilidad con rollback.
- Pruebas: 114 descubiertas y 114 aprobadas, incluidas las 5 integraciones PostgreSQL.
- Dry-run real v0.3 repetido: 893 filas, 2,497 items, archivo intacto y 0 escrituras empresariales.
- Ningún plan real fue aprobado/aplicado ni se publicó un release empresarial; no se modificó Odoo
  ni el Excel fuente y las ocho tablas empresariales siguen vacías.

### Próxima etapa por dependencias

1. Implementar la revisión y activación humana de productos y referencias aplicados; el publisher
   ya rechaza cualquier identidad que siga pendiente o no tenga referencia primaria aprobada.
2. Añadir reconciliación `update` campo por campo, con `before_values`, si la exportación completa
   aporta identidad Odoo estable; hasta entonces permanece bloqueada por diseño.
3. Continuar con imágenes, catálogo enriquecido y PWA/offline sobre releases inmutables.

### Sesión anterior: Inicialización del Proyecto (2026-08-17)

### Estado de Cumplimiento ✓

- ✓ Diagnóstico del entorno completado
- ✓ Repositorio Git inicializado
- ✓ Documentación base creada
- ✓ Estructura de carpetas planificada
- ✓ Reglas no negociables documentadas
- ✓ Muestra real de Odoo analizada preliminarmente
- ✓ Schema y migración validados en PostgreSQL
- ✓ Dry-run de Natsuki ejecutado sin escrituras empresariales
- ✓ MVP web local de consulta sobre la muestra funcionando
- ✓ Visor local detecta automáticamente el XLSX más reciente en `data/imports`
- ✓ Ficha individual web y ficha imprimible funcionando

### Completado en Esta Sesión

1. **Diagnóstico de Entorno**
   - Windows 11 Pro (Build 26200) - 64 bits
   - 237.41 GB libres en C:\
   - VS Code 1.133.0
   - Git 2.54.0
   - Python 3.14.5 disponible
   - Adobe InDesign 2026 presente
   - PostgreSQL y pgAdmin: NO instalados (fase posterior)

2. **Inicialización de Repositorio**
   - git init ejecutado
   - .gitignore configurado
   - Archivos de documentación creados:
     - PROJECT.md
     - AGENTS.md
     - HANDOFF.md (este archivo)
     - README.md
     - .env.example

3. **Documentación y validación**
   - Reglas no negociables documentadas
   - Estructura organizativa: empresa, marcas, fuente maestra
   - Funcionalidades: búsqueda, filtrado, generación de catálogos
   - Formatos de salida: web, PDF, InDesign
   - `docs/DATA_SPEC.md`: perfil preliminar de la muestra de 893 filas
   - Plan de importación persistido en `awaiting_review`

### Próximos Pasos (Orden de Prioridad)

#### FASE 1: Análisis de Datos (PRELIMINAR COMPLETADO)
- [x] Analizar muestra real de Excel de Odoo (Natsuki / Empaques)
- [x] Analizar estructura de columnas y completitud
- [x] Documentar campos observados en DATA_SPEC.md
- [ ] Obtener exportación completa de Odoo para ampliar la evidencia
- [ ] Identificar relaciones OEM, cross-reference, FMSI y aplicaciones vehiculares
- [ ] Convertir la especificación preliminar en contrato definitivo tras recibir más exportaciones

**Responsable**: Analista de Datos / Odoo  
**Dependencias actuales**: Exportación completa y/o nuevas muestras de Odoo

#### FASE 2: Diseño y Validación de Base de Datos
- [x] Diseñar schema de PostgreSQL preliminar
- [x] Definir tablas, relaciones, constraints e índices
- [x] Validar DDL y migración en PostgreSQL
- [ ] Revisar ajustes del schema contra la exportación completa

**Responsable**: Coordinador + Ingeniero Backend  
**Dependencias**: DATA_SPEC.md  
**Bloqueado por**: FASE 1  

#### FASE 3: Importador de Datos (Dry-run preliminar)
- [x] Importador Python para la muestra Excel/CSV
- [x] Validaciones, staging y resultados separados
- [x] Plan persistido con hash canónico y compuerta de aprobación
- [x] Control de imágenes sin decodificar ni modificar originales
- [ ] Ampliar reglas con la exportación completa de Odoo

**Responsable**: Ingeniero Backend  
**Dependencias**: Schema de BD  
**Bloqueado por**: FASE 2  

#### FASE 4: API Base
- [x] Búsqueda local por referencia y nombre
- [x] Filtro local por categoría
- [x] API HTTP formal con endpoints JSON
- [x] Read model publicado con UUID y checksum
- [ ] Endpoints de agrupación multinivel

**Responsable**: Ingeniero Backend  
**Dependencias**: BD con datos + Importador  
**Bloqueado por**: FASE 3  

#### FASE 5: Interfaz Web Local
- [x] Búsqueda por referencia y nombre
- [x] Filtro inicial por categoría
- [ ] Filtros multi-nivel
- [ ] Agrupación dinámica
- [x] Visualización de resultados de ficha básica

**Responsable**: Ingeniero Frontend  
**Dependencias**: API  
**Bloqueado por**: FASE 4  

#### FASE 6: Exportación de PDFs
- [ ] Generador de fichas PDF
- [ ] Compilación de catálogos PDF
- [ ] Metadatos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD con datos + API  
**Bloqueado por**: FASE 3  

#### FASE 7: Integración InDesign
- [ ] Scripts de InDesign
- [ ] Plantillas T4, T2, T1, TABLE, SEPARATOR
- [ ] Generación de documentos INDD
- [ ] Control de imágenes, fuentes, desbordamientos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD + Exportación PDF  
**Bloqueado por**: FASE 6  

### NO Hacer Todavía

- ❌ Ejecutar APPLY sin revisión y aprobación humana explícita
- ❌ Tratar la muestra de 893 filas como el catálogo completo
- ❌ Declarar definitivo el contrato del importador con la evidencia actual
- ❌ Tocar fotografías originales
- ❌ Modificar el Excel maestro de muestra

### Decisiones de Arquitectura Cerradas

| Decisión | Estado | Definición |
|----------|--------|------------|
| Base de datos | Cerrada | PostgreSQL es la base oficial. SQLite no será la base principal y solo podría usarse para pruebas aisladas si fuera necesario. |
| Backend | Cerrada | FastAPI es el backend oficial. |
| Frontend inicial | Cerrada | Jinja2 + HTML + CSS + JavaScript. React no se utilizará inicialmente. |
| Evolución | Cerrada | La arquitectura podrá evolucionar hacia un frontend separado si una necesidad real lo justifica. |

El frontend inicial debe ofrecer una interfaz premium, responsive y moderna. La ausencia inicial de React reduce complejidad y no limita el diseño.

### Decisiones Pendientes

| Decisión | Estado | Notas |
|----------|--------|-------|
| Formato Snapshots InDesign: XML vs JSON | Pendiente | Definir tras primer análisis de datos |
| Control de Versiones de Catálogos | Parcialmente cerrada | Releases inmutables, versionados y con checksum; falta definir la política operativa de publicación y retención. |

### Notas Técnicas

- Ruta del proyecto: `C:\PERFECT_CATALOG`
- MVP local: `http://127.0.0.1:8080`
- Lanzamiento: `INICIAR-SERVER.cmd` o `scripts/run_catalog_web.py`
- El MVP lee el Excel de muestra en modo solo lectura; no requiere contraseña ni conexión a PostgreSQL
- Al copiar una nueva exportación `.xlsx` a `data/imports`, el visor la recarga automáticamente en la siguiente consulta
- Ficha web: `/producto/<fila>`; versión imprimible: `/producto/<fila>/ficha`
- La ficha imprimible se puede guardar como PDF desde el navegador; no genera aún un PDF automatizado
- Usuario propietario: AzureAD\Diseño2
- Política de ejecución PowerShell: Bypass
- No se ejecuta como administrador (OK, no requerido)

### Contactos y Escalaciones

- **Bloqueos con Excel**: Contactar a Área de Odoo
- **Decisiones estratégicas**: Revisar con Gerencia
- **Cambios en reglas de negocio**: Actualizar PROJECT.md inmediatamente

### Última Actualización

- **Fecha**: 2026-08-17
- **Sesión**: Inicialización
- **Duración**: ~1 hora diagnóstico + setup
- **Próxima Revisión**: Tras obtener Excel de Odoo

---

### Cómo Usar Este Archivo

1. **Al Iniciar Sesión**: Lee este archivo completo
2. **Identifica Bloqueadores**: Busca items con ❌ o "Pendiente"
3. **Continúa desde Último Checkpoint**: Busca checkboxes [ ] sin marcar
4. **Antes de Cerrar Sesión**: Actualiza este archivo con tu progreso
5. **Comenta Decisiones**: Explica el "por qué" no solo el "qué"
