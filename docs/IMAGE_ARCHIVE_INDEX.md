# Índice no destructivo de imágenes

La migración `0009` y el comando `index-images` crean evidencia consultable de un ZIP de imágenes
aceptado en cuarentena. No extraen archivos al disco, no modifican el ZIP y no crean asociaciones con
productos.

## Uso

1. Aplicar `0007`, `0008` y después `MIGRAR-INDICE-IMAGENES.cmd`.
2. Ejecutar:

```powershell
.\.venv\Scripts\perfect-catalog.exe index-images <SUBMISSION_UUID> `
  --actor <USUARIO> --reason "Paquete autorizado para indexación" --prompt-password
```

La operación vuelve a verificar ruta confinada, tamaño y SHA-256 del objeto content-addressed. Lee
cada miembro por streaming y registra ruta, nombre, extensión, MIME, tamaños, CRC32 y SHA-256 del
contenido. El ZIP nunca se sirve ni se extrae.

## Conflictos y revisión

La clave de búsqueda deriva únicamente del nombre del archivo: Unicode normalizado, mayúsculas y
separadores convertidos a guiones. Es una ayuda de búsqueda, no identidad empresarial.

- clave única dentro del ZIP: `unmatched`;
- clave repetida: todas las entradas del grupo quedan `ambiguous` y conservan su conteo.

No existe estado `matched` en este bloque. No se escriben `media_asset` ni `product_media`; cualquier
asociación futura requerirá candidatos separados, evidencia exacta y revisión humana individual.
