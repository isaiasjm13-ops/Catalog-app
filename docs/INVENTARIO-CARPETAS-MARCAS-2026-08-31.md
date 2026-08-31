# Inventario de carpetas candidatas a Brand

Fuente leída en modo de sólo lectura el 2026-08-31:

- `\\192.168.1.86\Diseño_Files\PERFECT\HIGH RES`
- `\\192.168.1.86\Diseño_Files\PDM\HIGH RES`

Este inventario no crea Brands ni demuestra propiedad comercial por sí solo. Una carpeta puede ser
marca, categoría, línea, agrupador de trabajo o nombre histórico.

## Resumen de calidad

- Perfect: 29 carpetas.
- PDM: 89 carpetas.
- Nombres presentes en ambos árboles: `ASIA INC` y `KDT`.
- Conflictos de jerarquía con la especificación: `KMC`, `MASAKI` y `NATSUKI` aparecen físicamente
  bajo Perfect, aunque el modelo de negocio los define como Companies con sus propias Brands.
- Agrupadores probables que no deben convertirse automáticamente en Brand:
  `GENERICO`, `moto`, `MOTORES Y RING`, `VARIANTES`, `ENGINE VALVE`, `ENGINES NEARING`,
  `GENUINE`, `GENUINE PARTS-AUTO PARTS`, `MOTOR`, `NUEVAS`, `OEM`, `OIL SEALS`.

## Perfect - candidatos observados

`ASIA INC`, `CLIPSE`, `DIAMOND`, `ECLIPSE`, `EXACT CARS`, `FCB`, `FUKA`, `GENERICO`,
`GLOBAL OIL SEALS`, `IRIDIUM`, `JF`, `KAZE`, `KDT`, `KMC`, `KOSYN`, `MASAKI`, `MEGA ENGINE`,
`moto`, `MOTORES Y RING`, `NAKAMOTO`, `NATSUKI`, `NECCO`, `NTS`, `REVVSUN`, `SALJO`,
`SHIMATAKA`, `TAKASHI`, `UNIPOINT`, `VARIANTES`.

Decisiones ya confirmadas:

- `EXACT CARS` corresponde a Brand `EXACTCARS` y pertenece a Perfect Company.
- La presencia física de una carpeta no reasigna automáticamente las demás.

## PDM - candidatos observados

`555`, `ADVICS`, `AISAN`, `AISIN`, `ART`, `ASIA INC`, `BEN`, `BEN BRAND`, `BLK`, `CAR-DEX`,
`CENTURY`, `CHAMPION`, `DAIDO METAL`, `DENSO`, `DOOWON`, `EAGLE`, `ENGINE VALVE`,
`ENGINES NEARING`, `FAG`, `FLAMMA`, `GATES`, `GENUINE`, `GENUINE ISUZU`,
`GENUINE PARTS-AUTO PARTS`, `GENUINE SUZUKI`, `GENUINE TOYOTA`, `GMB`, `HALLA`, `HAN`,
`HI-Q`, `HITACHI`, `HYUNDAI GENUINE PARTS`, `ILJIN`, `JOINT FUJI`, `JTEKT`, `KDT`, `KEYSTER`,
`KOBE`, `KOYO`, `KP`, `KPR`, `KYOSAN`, `LUK`, `MIYACO`, `MOBIS`, `MONROE`, `MOOG`, `MOTOR`,
`MOTORCRAFT`, `MRK`, `MSB`, `MUSASHI`, `NACHI`, `NEW ERA`, `NISTO`, `NPR`, `NPW`, `NSK`,
`NTN`, `NUEVAS`, `OBC`, `OEM`, `OIL SEALS`, `OSK`, `PMC`, `RAON`, `REEVSUN`, `SAFETY`,
`SEIWA`, `SHIBAMI`, `SHIMAHIDE`, `SUIKO`, `TAMA`, `TBK`, `TEIKIN`, `THO`, `THO OIL SEAL`,
`THREE FIVE`, `TOKICO`, `TRC`, `TSK`, `TZK`, `VALEO`, `WAGNER`, `YEC`, `YPR`, `ZETRA`,
`ZEXEL`, `ZUIKO`.

## Reglas para la futura incorporación

1. Comparar cada nombre con Odoo y archivos de producto; la carpeta de imágenes no es fuente
   maestra de pertenencia.
2. Clasificar como `brand_confirmed`, `grouping_only`, `alias`, `collision` o `unresolved`.
3. Resolver `ASIA INC` y `KDT` antes de crear FK: pueden ser copias, líneas compartidas o marcas
   administradas en contextos distintos.
4. Resolver por separado `KMC`, `MASAKI` y `NATSUKI`; su ubicación bajo Perfect puede ser legado
   operativo y no propiedad comercial.
5. No crear automáticamente carpetas genéricas/OEM como Brands.
6. Conservar nombres originales, pero generar código normalizado sólo después de aprobar el mapping.
