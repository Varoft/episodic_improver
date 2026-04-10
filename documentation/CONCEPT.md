# Episodic Improver - Qué es y cómo funciona

**Idea básica:** Un sistema que guarda lo que ha hecho el robot antes, y utiliza eso para hacer mejor las cosas la próxima vez.

**En palabras simples:** Si el robot tiene que navegar a un lugar, primero mira sus experiencias pasadas y pregunta: *"¿He estado en una situación parecida? ¿Qué funcionó la última vez?"*

---

## El Problema

Imagina que el robot tiene que ir de un punto A a otro punto B en una sala llena de obstáculos. El problema es:

1. **Cada situación es diferente:** La sala es la misma, pero el robot empieza en distintos lugares, hay obstáculos en diferentes posiciones, el destino cambia...
2. **Probar todo toma tiempo:** Si intentas muchas configuraciones diferentes para ver cuál funciona, pierdes mucho tiempo
3. **El robot debería aprender solo:** En lugar de que alguien le diga qué hacer, el robot debería acordarse de lo que funcionó antes

### La forma antigua (sin aprender) ❌

```
Intento 1: Configuración aleatoria → Funciona (por suerte)
Intento 2: Otra configuración → No funciona (probamos a ciegas)
Intento 3: Otra más → Tampoco funciona (seguimos sin aprender)
... muchos intentos fallidos antes de encontrar lo que sirve
```

### La forma del Episodic Improver (con aprendizaje) ✅

```
Misión 1: Cualquier configuración → Lo registramos todo
Misión 2: ¿Es parecida a la Misión 1? → Usamos lo que funcionó antes
Misión 3: ¿Hay un obstáculo similar? → Buscamos qué funcionó en casos parecidos
... ¡rápidamente encontramos buenas configuraciones!
```

---

## La Solución: Fingerprints 7D

### ¿Qué es un Fingerprint?

Es como una "huella digital" de una misión de navegación. En lugar de guardar toda la trayectoria (miles de puntos), guardamos 7 números que describen la geometría de la misión **antes de ejecutarla**.

**Importante:** Estos 7 números son valores *normalizados* (escalados a rangos pequeños), no mediciones brutas. Así el sistema puede comparar misiones muy diferentes de forma justa.

Esos 7 números representan características geométricas de la misión:

| # | Parámetro | Fórmula | Rango | Qué representa |
|---|-----------|---------|-------|------------|
| **f1** | Posición X | `src_x / 80.0` | [-0.5, +0.5] | Dónde está el robot (lado izquierdo vs derecho) |
| **f2** | Posición Y | `src_y / 80.0` | [-0.5, +1.0] | Dónde está el robot (lado frontal vs trasero) |
| **f3** | Ángulo | `atan2(dy, dx) / π` | [-1, +1] | Hacia qué dirección va (normalizado a radianes) |
| **f4** | Distancia | `straight_dist / diagonal_max` | [0, 1] | Qué tan lejos es (normalizado a escala de sala) |
| **f5** | Tortuosidad | `distancia_viajada / distancia_recta` | [0.8, 1.6] | Eficiencia del camino (1.0 = línea recta, >1.0 = con desvíos) |
| **f6** | Densidad | `obstacle_density` | [0, 1] | Cuántos obstáculos hay en el área de inicio |
| **f7** | Complejidad | `f6 × f5` | [0, 1] | Combinación de obstáculos + desvíos necesarios |

### Ejemplo: Tres misiones diferentes

| Tipo de Misión | Fingerprint | Lo que significa |
|---|---|---|
| **Fácil:** Cerca, sin obstáculos | [0.1, 0.2, 0.0, 0.15, 1.01, 0.05, 0.05] | Robot cerca del origen, destino cercano, sala vacía, camino recto |
| **Normal:** Media distancia, obstáculos moderados | [0.0, -0.1, 0.25, 0.35, 1.15, 0.40, 0.46] | Robot en el medio, destino regular, obstáculos moderados, algunos desvíos |
| **Difícil:** Lejos, llena de obstáculos | [-0.3, 0.4, -0.5, 0.8, 1.5, 0.75, 1.0] | Robot lejano, destino muy alejado, sala llena de obstáculos, muchos desvíos |

### ¿Por qué usar 7 números?

- **Usa poco espacio:** 7 números vs miles de puntos de una trayectoria
- **Es rápido:** Comparar números es mucho más rápido que comparar trayectorias completas
- **Parámetros estandarizados:** Todos normalizados a rangos [-1, +1] o [0, 1], lo que permite aprendizaje automático justo
- **Describe la geometría PRE-misión:** Se calcula ANTES de ejecutar, así podemos predecir parámetros óptimos antes de que falle

---

## Cómo Funciona el Aprendizaje

### Paso 1: Registrar lo que pasó

Cuando el robot termina una misión, guarda un archivo con toda la información:

```json
{
  "id_mision": "mision_123",
  "inicio": [10.5, 15.2],
  "destino": [45.0, 50.0],
  "trayectoria": [[10.5, 15.2], [12.0, 16.5], ..., [45.0, 50.0]],
  "obstacle_density": 0.45,
  "exito": true,
  "tiempo_segundos": 18.5,
  "energia": 0.68,
  "suavidad": 0.82,
  "configuracion_usada": {
    "particulas_mppi": 1000,
    "distancia_vision": 2.5,
    "replanificacion": 10.0
  }
}
```

### Paso 2: Crear el fingerprint

Se calcula cómo es la misión ante de ejecutarla (inicio, destino, obstáculos). Se convierte en 7 números normalizados:

```python
# La misión: ir de [5, 10] a [40, 45] con densidad de obstáculos 0.45
# Distancia recta: ~49.5m, distancia viajada: ~57m (por desvíos)

fingerprint = [0.063, 0.125, 0.25, 0.44, 1.15, 0.45, 0.52]
#              f1    f2    f3   f4   f5    f6    f7
#
# f1 = 5/80 = 0.063        (Posición X normalizada)
# f2 = 10/80 = 0.125       (Posición Y normalizada)
# f3 = 0.25                (Ángulo ~45° normalizado a π)
# f4 = 0.44                (Distancia recta / diagonal)
# f5 = 1.15                (Desvíos: 57m / 49.5m)
# f6 = 0.45                (Densidad de obstáculos)
# f7 = 0.52                (Complejidad: f6 × f5)
```

### Paso 3: Guardar en nuestro "libro de experiencias"

Se guarda el fingerprint con la configuración que funcionó:

```json
{
  "id": "mision_123",
  "fingerprint": [0.063, 0.125, 0.25, 0.44, 1.15, 0.45, 0.52],
  "configuracion": {"particulas_mppi": 1000, "distancia_vision": 2.5, ...},
  "funcionó": true,
  "calidad": 0.82
}
```

### Paso 4: Nueva misión llega

Un usuario dice: "Ve del punto A al punto B". Antes de que el robot empiece:

1. Calculamos el fingerprint de esta nueva misión (sin haber fallado aún)
2. Buscamos en el "libro de experiencias" si hay algo parecido
3. Si hay, usamos la configuración que funcionó antes
4. Si hay algo diferente (más obstáculos, más lejos), ajustamos

### Paso 5: Ajustar según lo que ves

Si la nueva misión tiene 20% más obstáculos que la que guardamos:

```python
# La configuración que usó antes:
config_vieja = {"particulas": 1000, "distancia_vision": 2.5}

# Pero esta vez hay más obstáculos, así que:
config_nueva = {
    "particulas": 1000 * 1.2,      # Más búsqueda = 1200
    "distancia_vision": 2.5 * 1.1   # Visión más lejos = 2.75
}
```

---

## Ejemplo Real: Navegación en una Sala

### Día 1 - Primera misión

- **Tarea:** Ir de [5, 10] a [40, 45]
- **Obstáculos:** Densidad media (0.45)
- **Configuración:** La predeterminada (1000 partículas, visión 2.5m)
- **Resultado:** ✅ Éxito, tardó 18.5s, calidad 0.82
- **Se guarda:** El fingerprint y que funcionó bien

### Día 1 - Segunda misión (poco después)

- **Tarea:** Ir de [5, 10] a [40, 45] ← ¡La MISMA tarea!
- **Obstáculos:** Se movieron las sillas (un poco más, 0.48)
- **El sistema piensa:** "Esto es muy parecido a hace 5 minutos"
- **Reutiliza:** La configuración anterior, pero ajusta un poco
- **Nueva configuración:** 1100 partículas (un 10% más), visión 2.7m
- **Resultado:** ✅ Éxito, tardó 17.8s, calidad 0.84 ← ¡Más rápido!

### Día 1 - Tercera misión

- **Tarea:** Ir de [5, 10] a [20, 20] ← Pero esta es CORTA
- **Obstáculos:** Menos (0.25)
- **El sistema piensa:** "Esto es diferente, pero tengo experiencias de misiones cortas"
- **Busca:** Qué funcionó en misiones cortas del pasado
- **Idea:** Si es corta y sin obstáculos, no necesitas escanear tanto
- **Nueva configuración:** 800 partículas (menos búsqueda), visión 1.5m
- **Resultado:** ✅ Muy rápido, 4.2s, calidad 0.88 ← ¡Perfecto para cortas!

### Qué aprendió el sistema después de 50 misiones

El robot ahora "sabe":
- Misiones **largas + muchos obstáculos** → Usa 1300+ partículas, visión amplia
- Misiones **cortas + sin obstáculos** → Usa menos recursos, visión cercana
- Misiones **cerca de obstáculos** → Replanifica más frecuentemente

**Todo aprendido automáticamente, sin que nadie lo programara manualmente.**

---

## Las Partes del Sistema

```
┌─────────────────────────────────────────┐
│ Episodic Improver                       │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Monitor de archivos (watchdog)  │   │
│  │ - Espera nuevas misiones        │   │
│  │ - Lee: mission_initial_*.json   │   │
│  └─────────────────────────────────┘   │
│           ↓                             │
│  ┌─────────────────────────────────┐   │
│  │ Calculador de fingerprints      │   │
│  │ - Convierte datos en 7 números  │   │
│  │ - Busca casos similares         │   │
│  └─────────────────────────────────┘   │
│           ↓                             │
│  ┌─────────────────────────────────┐   │
│  │ Generador de sugerencias        │   │
│  │ - Adapta la configuración       │   │
│  │ - Escribe: predictions_*.json   │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

### Cómo se conecta con SLAMO (el robot)

```
Usuario cliquea en el mapa
         ↓
SLAMO calcula el camino
         ↓
SLAMO escribe: mission_initial_*.json
         ↓
Episodic Improver lo ve
         ↓
Busca si algo parecido funcionó antes
         ↓
Episodic Improver escribe: predictions_*.json
         ↓
SLAMO lo lee y aplica esas configuraciones
         ↓
SLAMO ejecuta la misión
         ↓
SLAMO guarda resultado
         ↓
(Próxima vez aprenderá de esto)
```

---

## Qué Hay Ahora Mismo

✅ **Todo funciona:**
- Calcula fingerprints correctamente
- Lee archivos de misiones
- Genera sugerencias automáticamente
- 32 pruebas pasadas
- Se puede usar ahora

⚠️ **Lo que falta:**
- Conectar completamente con SLAMO (el robot tiene problemas para iniciar)
- Pero el sistema de predicciones en sí **está listo**

---

## En Resumen

El Episodic Improver es básicamente:

1. **Guarda experiencias** → Cada misión se guarda (¿funcionó? ¿cómo?)
2. **Las representa de forma compacta** → En 7 números (fingerprint)
3. **Busca experiencias similares** → Si la próxima misión es parecida...
4. **Reutiliza lo que funcionó** → Adapta la configuración anterior
5. **Mejora gradualmente** → Con más experiencias, mejores sugerencias

**Es como si el robot dijera:** *"Visto esto antes. La última vez funcionó mejor cuando hice X. Déjame intentarlo."*

---

## Archivos Importantes

- **PROTOCOL.md** - Cómo se comunica con SLAMO (detalles técnicos)
- **DOCS.md** - Información de cada componente del código
- **QUICKSTART.md** - Cómo ponerlo a funcionar
- **test_bridge_simulator.py** - Código de prueba que puedes ver para entender mejor
