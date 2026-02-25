# Smoke test manual — Asistente IA (PROM-9)

1. Abrir la app PROM-9.
2. Ir a **Herramientas → Asistente IA…** y verificar que abre el diálogo.
3. Completar:
   - Tipo de maestro: **Perfil**.
   - Nombre: `perfil_demo_ia`.
   - Descripción: texto funcional en español.
4. Pulsar **Generar**.
   - Verificar estado **Generando…** y luego JSON en vista previa.
5. Pulsar **Aplicar al formulario**.
   - Confirmar apertura del editor de Perfil.
   - Ajustar algún campo y guardar en el editor.
6. Pulsar **Guardar en maestros**.
   - Verificar mensaje de éxito.
   - Comprobar que el perfil aparece en selectores.
7. Repetir para **Contexto** y **Plantilla**:
   - En Plantilla, validar que se crea/actualiza el registro y existe `<nombre>.py` en templates per-user.
8. Caso de sobreescritura:
   - Intentar guardar el mismo nombre y confirmar que aparece diálogo de confirmación.
9. Caso sin API key:
   - Lanzar sin `OPENAI_API_KEY` y verificar error claro.
10. Caso sin dependencia `openai`:
    - Simular entorno sin paquete y verificar error claro sin cierre inesperado.


## Smoke test breve del flujo guiado (nuevo)

1. En **Asistente IA**, elegir **Profundidad: Profundo** y completar Nombre + Descripción con dictado (🎤).
2. Pulsar **Diagnosticar** y verificar:
   - aparecen preguntas,
   - se habilita **Generar maestro**,
   - se muestra `draft` en vista previa.
3. En respuestas, escribir por ejemplo:
   - `herramientas: Jira;Slack`
   - `prioridades: ["calidad","tiempo"]`
   - `empresa: ACME`
   y pulsar **Refinar**.
4. Verificar que **Memoria confirmada** muestra el diccionario acumulado y que no se bloquean botones si ocurre error.
5. Pulsar **Generar maestro** y confirmar JSON final estricto en vista previa.
