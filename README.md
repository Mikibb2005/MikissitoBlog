# MikissitoBlog

Blog estático en español con el aspecto sencillo de una página personal de principios de los 2000. El sitio publicado usa HTML y CSS, por lo que puede alojarse en GitHub Pages sin PHP ni servidor.

## Publicar en GitHub Pages

1. Sube el contenido del repositorio a GitHub.
2. En **Settings → Pages**, selecciona **Deploy from a branch**, la rama `main` y la carpeta `/(root)`, y pulsa **Save**.
3. Las páginas de review y entrenamiento creadas por la herramienta también deben añadirse y subirse al repositorio.

El sitio no incluye un foro interactivo ni guarda datos por sí solo: GitHub Pages sirve archivos estáticos. Las reviews y los informes semanales son páginas HTML generadas localmente.

## Crear reviews e informes semanales

Requiere Python 3.7 o posterior con Tkinter. No necesita instalar paquetes:

```powershell
python tools\generador.py
```

La ventana **Developer Desk** permite:

- Crear una review con título, juego, imagen, fecha, puntuación, plataforma, género, texto y pros/contras. Se genera `reviews\<slug>.html` y se añade una tarjeta a `reviews\index.html`.
- Preparar un informe de lunes a domingo, añadir datos y notas por día, resumen y objetivo semanal. Se genera `entrenamiento\semana-AAAA-MM-DD.html` y se añade al índice semanal.
- Intentar importar tablas y datos JSON visibles desde la URL de CSStats. Es una petición HTTP normal; no automatiza una sesión ni intenta superar CAPTCHA o verificaciones anti-bots. Si el sitio la bloquea, la aplicación muestra el error y el enlace del perfil para continuar manualmente. Los datos importados sin fecha quedan separados del registro diario para no atribuirlos a un día incorrecto.

Las estadísticas diarias se escriben por día; los datos visibles importados sin fechas aparecen como una captura general del perfil. El generador no inventa métricas ni las calcula a partir de datos incompletos. Revisa el contenido generado antes de publicarlo.

## Estructura

- `index.html`: portada.
- `reviews\index.html`: índice de reviews.
- `entrenamiento\index.html`: índice de informes semanales.
- `css\style.css`: estilos compartidos.
- `tools\generador.py`: aplicación local de escritorio.
