#!/usr/bin/env python3
"""Generador local de reviews y diarios semanales para MikissitoBlog."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parents[1]
REVIEWS_DIR = ROOT / "reviews"
TRAINING_DIR = ROOT / "entrenamiento"
DEFAULT_PROFILE = "https://csstats.gg/player/76561198840688911#/"
USER_AGENT = "MikissitoBlog-local-generator/1.0"


def escape(value: str) -> str:
    return html.escape(value.strip(), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Escribe un título válido para crear el nombre del archivo.")
    return slug


def multiline(value: str) -> str:
    return "<br>\n".join(escape(line) for line in value.strip().splitlines())


class TableParser(HTMLParser):
    """Extrae tablas y bloques JSON-LD de una página accesible sin ejecutar JavaScript."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.current_table: list[list[str]] | None = None
        self.current_row: list[str] | None = None
        self.cell: list[str] | None = None
        self.json_ld: list[str] = []
        self.in_json_ld = False
        self.script_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self.current_table = []
        elif tag == "tr" and self.current_table is not None:
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.cell = []
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self.in_json_ld = True
            self.script_text = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.in_json_ld:
            self.script_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.current_row is not None:
            text = " ".join(" ".join(self.cell).split())
            self.current_row.append(text)
            self.cell = None
        elif tag == "tr" and self.current_row is not None and self.current_table is not None:
            if any(self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.current_table is not None:
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag == "script" and self.in_json_ld:
            self.json_ld.append("".join(self.script_text))
            self.in_json_ld = False


def fetch_profile(url: str) -> list[str]:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in {"csstats.gg", "www.csstats.gg"}:
        raise ValueError("Introduce un enlace HTTPS de csstats.gg.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise OSError(f"CSStats respondió con el código HTTP {response.status}.")
            page = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        raise OSError(f"CSStats respondió con el código HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise OSError(f"No se pudo conectar con CSStats: {error.reason}") from error

    if "challenge-platform" in page.lower() or "verificación de seguridad" in page.lower():
        raise OSError("CSStats mostró una verificación de seguridad y no permitió leer las estadísticas.")

    parser = TableParser()
    parser.feed(page)
    extracted: list[str] = []
    for table in parser.tables:
        for row in table:
            if len(row) >= 2:
                extracted.append(f"{row[0]}: {' | '.join(row[1:])}")
            elif row:
                extracted.append(row[0])

    for block in parser.json_ld:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            extracted.extend(f"{key}: {value}" for key, value in payload.items() if isinstance(value, (str, int, float)))
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    extracted.extend(
                        f"{key}: {value}" for key, value in item.items() if isinstance(value, (str, int, float))
                    )

    if not extracted:
        raise OSError("La página no expone tablas o datos JSON legibles sin ejecutar scripts.")
    return list(dict.fromkeys(extracted))


def write_review(data: dict[str, str]) -> Path:
    title = data["title"].strip()
    if not title:
        raise ValueError("El título de la review es obligatorio.")
    slug = slugify(title)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    output = REVIEWS_DIR / f"{slug}.html"
    if output.exists():
        raise FileExistsError(f"Ya existe una review llamada «{slug}». Cambia el título o elimina la página anterior.")

    score = escape(data["score"]) or "—"
    image = data["image"].strip()
    if image and urlparse(image).scheme not in {"https", "http"}:
        raise ValueError("La portada debe usar una URL HTTP o HTTPS.")
    image_html = (
        f'<img class="review-cover" src="{escape(image)}" alt="Portada de {escape(title)}">'
        if image else '<div class="review-cover cover-placeholder">PORTADA NO DISPONIBLE</div>'
    )
    pros = [item.strip() for item in data["pros"].splitlines() if item.strip()]
    cons = [item.strip() for item in data["cons"].splitlines() if item.strip()]

    def list_items(items: list[str]) -> str:
        if not items:
            return "<li>Pendiente de completar</li>"
        return "\n".join(f"<li>{escape(item)}</li>" for item in items)

    review_html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} — MikissitoBlog</title><link rel="stylesheet" href="../css/style.css">
</head>
<body>
  <header class="site-header"><a class="brand" href="../index.html"><span class="brand-mark">MB</span><span>MikissitoBlog<small>GAME LOG // EST. 1999</small></span></a><nav class="main-nav" aria-label="Navegación principal"><a href="../index.html">Inicio</a><a class="active" href="index.html">Reviews</a><a href="../entrenamiento/index.html">Entrenamiento</a></nav></header>
  <main>
    <section class="page-heading"><p class="eyebrow">REVIEW // {escape(data["date"])}</p><h1>{escape(title)}<span class="heading-dot">.</span></h1><p>{escape(data["platform"])} // {escape(data["genre"])}</p></section>
    <article class="panel review-layout">{image_html}<div><p class="eyebrow">PUNTUACIÓN</p><p class="review-score">{score}<span> / 10</span></p><p class="eyebrow">SOBRE EL JUEGO</p><p>{multiline(data["review"]) or "Review pendiente de completar."}</p></div></article>
    <section class="home-grid review-points"><article class="panel"><p class="eyebrow">01 // LO MEJOR</p><h2>Pros</h2><ul>{list_items(pros)}</ul></article><article class="panel"><p class="eyebrow">02 // POR MEJORAR</p><h2>Contras</h2><ul>{list_items(cons)}</ul></article></section>
    <p><a class="text-link" href="index.html">← VOLVER A REVIEWS</a></p>
  </main>
  <footer class="site-footer"><span>MIKISSITOBLOG</span><span>REVIEW // {escape(data["game"])}</span></footer>
</body></html>
"""
    output.write_text(review_html, encoding="utf-8")
    add_review_card(output.name, title, data)
    return output


def add_review_card(filename: str, title: str, data: dict[str, str]) -> None:
    index = REVIEWS_DIR / "index.html"
    source = index.read_text(encoding="utf-8")
    marker = "    <!-- GENERATED REVIEWS -->"
    card = f"""    <article class="panel review-card">
      <p class="eyebrow">REVIEW // {escape(data["date"])} // {escape(data["platform"])}</p>
      <h2><a href="{escape(filename)}">{escape(title)}</a></h2>
      <p>{escape(data["genre"])} · {escape(data["score"])}/10</p>
      <a class="text-link" href="{escape(filename)}">LEER REVIEW ↗</a>
    </article>
"""
    if marker in source:
        source = source.replace(marker, marker + "\n" + card.rstrip(), 1)
    else:
        raise ValueError("No se encontró el marcador de reviews generadas en reviews/index.html.")
    source = re.sub(r"\s*<!-- EMPTY REVIEWS START -->.*?<!-- EMPTY REVIEWS END -->", "", source, count=1, flags=re.DOTALL)
    index.write_text(source, encoding="utf-8")


def week_dates(start_text: str) -> list[date]:
    try:
        start = datetime.strptime(start_text, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("La fecha inicial debe tener el formato AAAA-MM-DD.") from error
    if start.weekday() != 0:
        raise ValueError("La fecha inicial debe ser un lunes para que el informe cubra lunes-domingo.")
    return [start + timedelta(days=offset) for offset in range(7)]


def write_week(data: dict[str, str], days: list[dict[str, str]]) -> Path:
    dates = week_dates(data["week_start"])
    end = dates[-1]
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"semana-{dates[0].isoformat()}.html"
    output = TRAINING_DIR / filename
    if output.exists():
        raise FileExistsError(f"Ya existe el informe {filename}.")
    weekly_rows = []
    day_cards = []
    day_names = ("LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO")
    for day_name, day, entry in zip(day_names, dates, days):
        sessions = multiline(entry["stats"]) or "Sin estadísticas registradas."
        notes = multiline(entry["notes"]) or "Sin notas."
        weekly_rows.append(f"<tr><th>{day_name} {day.strftime('%d/%m')}</th><td>{sessions}</td></tr>")
        day_cards.append(
            f'<article class="panel day-card"><p class="eyebrow">{day_name} // {day.strftime("%d/%m/%Y")}</p>'
            f'<h2>{escape(entry["title"]) or "Registro del día"}</h2><p>{notes}</p>'
            f'<details><summary>ESTADÍSTICAS DEL DÍA</summary><p>{sessions}</p></details></article>'
        )
    week_html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Semana {dates[0].isoformat()} — MikissitoBlog</title><link rel="stylesheet" href="../css/style.css"></head>
<body>
  <header class="site-header"><a class="brand" href="../index.html"><span class="brand-mark">MB</span><span>MikissitoBlog<small>GAME LOG // EST. 1999</small></span></a><nav class="main-nav" aria-label="Navegación principal"><a href="../index.html">Inicio</a><a href="../reviews/index.html">Reviews</a><a class="active" href="index.html">Entrenamiento</a></nav></header>
  <main><section class="page-heading"><p class="eyebrow">CS2 // SEMANA {dates[0].strftime("%d/%m")} — {end.strftime("%d/%m/%Y")}</p><h1>Weekly Report<span class="heading-dot">.</span></h1><p>{escape(data["focus"]) or "Resumen de entrenamiento y partidas de la semana."}</p></section>
    <section class="stats-strip"><div><span class="stat-label">PERIODO</span><strong>{dates[0].strftime("%d/%m/%Y")} — {end.strftime("%d/%m/%Y")}</strong></div><div><span class="stat-label">FUENTE</span><strong>CSSTATS / REGISTRO MANUAL</strong></div><div><span class="stat-label">ENLACE DE PERFIL</span><strong><a href="{escape(data["profile_url"])}">ABRIR CSSTATS ↗</a></strong></div></section>
    <section class="panel"><p class="eyebrow">RESUMEN // DATOS POR DÍA</p><div class="table-wrap"><table><tbody>{"".join(weekly_rows)}</tbody></table></div></section>
    {f'<section class="panel profile-snapshot"><p class="eyebrow">CSSTATS // DATOS DE PERFIL SIN FECHA</p><p>{multiline(data["profile_stats"])}</p><p class="tag">DATOS GENERALES // NO ATRIBUIDOS A UN DÍA</p></section>' if data["profile_stats"].strip() else ""}
    <section class="day-grid">{"".join(day_cards)}</section>
    <section class="panel"><p class="eyebrow">REVIEW DE LA SEMANA</p><h2>Qué mantener / qué mejorar</h2><p>{multiline(data["summary"]) or "Añade aquí una conclusión de la semana."}</p></section>
    <p><a class="text-link" href="index.html">← VOLVER AL DIARIO</a></p>
  </main><footer class="site-footer"><span>MIKISSITOBLOG</span><span>TRAINING // REVIEW // REPEAT</span></footer>
</body></html>
"""
    output.write_text(week_html, encoding="utf-8")
    add_week_card(filename, dates[0], end, data)
    return output


def add_week_card(filename: str, start: date, end: date, data: dict[str, str]) -> None:
    index = TRAINING_DIR / "index.html"
    source = index.read_text(encoding="utf-8")
    marker = "    <!-- GENERATED WEEKS -->"
    card = f"""    <article class="panel week-card">
      <p class="eyebrow">CS2 // SEMANA {start.strftime("%d/%m")} — {end.strftime("%d/%m/%Y")}</p>
      <h2><a href="{escape(filename)}">{escape(data["focus"]) or "Weekly Report"}</a></h2>
      <a class="text-link" href="{escape(filename)}">ABRIR INFORME ↗</a>
    </article>
"""
    if marker not in source:
        raise ValueError("No se encontró el marcador de informes semanales en entrenamiento/index.html.")
    source = source.replace(marker, marker + "\n" + card.rstrip(), 1)
    source = re.sub(r"\s*<!-- EMPTY WEEKS START -->.*?<!-- EMPTY WEEKS END -->", "", source, count=1, flags=re.DOTALL)
    index.write_text(source, encoding="utf-8")


class GeneratorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MikissitoBlog // Developer Desk")
        self.geometry("920x760")
        self.minsize(720, 600)
        self.configure(bg="#101316")
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#101316")
        self.style.configure("TLabel", background="#101316", foreground="#e7e8e4", font=("Segoe UI", 10))
        self.style.configure("TNotebook", background="#101316", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#20272c", foreground="#d4dfdf", padding=(14, 9), font=("Consolas", 10, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", "#79b9cc")], foreground=[("selected", "#101316")])
        self.style.configure("TButton", background="#79b9cc", foreground="#101316", padding=(12, 8), font=("Consolas", 10, "bold"))
        self.style.configure("TEntry", fieldbackground="#20272c", foreground="#e7e8e4")
        self.style.configure("TCombobox", fieldbackground="#20272c", foreground="#e7e8e4")

        header = ttk.Frame(self, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="MIKISSITOBLOG // DEVELOPER DESK", font=("Consolas", 14, "bold"), foreground="#79b9cc").pack(anchor="w")
        ttk.Label(header, text="Crea páginas HTML locales listas para publicar en GitHub Pages.", foreground="#9da8aa").pack(anchor="w", pady=(5, 0))
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.review_tab = ttk.Frame(self.tabs, padding=18)
        self.week_tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(self.review_tab, text="NUEVA REVIEW")
        self.tabs.add(self.week_tab, text="INFORME CS2")
        self.create_review_form()
        self.create_week_form()

    def field(self, parent: ttk.Frame, label: str, row: int, value: str = "") -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=6)
        entry = ttk.Entry(parent)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        entry.insert(0, value)
        parent.columnconfigure(1, weight=1)
        return entry

    def text_field(self, parent: ttk.Frame, label: str, row: int, height: int = 4) -> tk.Text:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=6)
        text = tk.Text(parent, height=height, wrap="word", bg="#20272c", fg="#e7e8e4", insertbackground="#e7e8e4", relief="flat", padx=8, pady=7)
        text.grid(row=row, column=1, sticky="ew", pady=6)
        parent.columnconfigure(1, weight=1)
        return text

    @staticmethod
    def read_text(widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip()

    def create_review_form(self) -> None:
        form = self.review_tab
        self.review_title = self.field(form, "Título *", 0)
        self.review_game = self.field(form, "Juego", 1)
        self.review_date = self.field(form, "Fecha (AAAA-MM-DD)", 2, date.today().isoformat())
        self.review_platform = self.field(form, "Plataforma", 3)
        self.review_genre = self.field(form, "Género", 4)
        self.review_score = self.field(form, "Puntuación / 10", 5)
        self.review_image = self.field(form, "URL de portada (opcional)", 6)
        self.review_body = self.text_field(form, "Review", 7, 6)
        self.review_pros = self.text_field(form, "Pros (uno por línea)", 8, 3)
        self.review_cons = self.text_field(form, "Contras (uno por línea)", 9, 3)
        ttk.Button(form, text="GENERAR PÁGINA DE REVIEW", command=self.generate_review).grid(row=10, column=1, sticky="e", pady=(14, 0))

    def generate_review(self) -> None:
        values = {
            "title": self.review_title.get(),
            "game": self.review_game.get(),
            "date": self.review_date.get(),
            "platform": self.review_platform.get(),
            "genre": self.review_genre.get(),
            "score": self.review_score.get(),
            "image": self.review_image.get(),
            "review": self.read_text(self.review_body),
            "pros": self.read_text(self.review_pros),
            "cons": self.read_text(self.review_cons),
        }
        try:
            path = write_review(values)
        except (OSError, ValueError) as error:
            messagebox.showerror("No se pudo generar la review", str(error))
            return
        messagebox.showinfo("Review generada", f"Página creada y añadida al índice:\n{path}")

    def create_week_form(self) -> None:
        form = self.week_tab
        self.profile_url = self.field(form, "Perfil CSStats", 0, DEFAULT_PROFILE)
        self.week_start = self.field(form, "Lunes de la semana (AAAA-MM-DD)", 1, self.monday_of_current_week().isoformat())
        ttk.Button(form, text="INTENTAR IMPORTAR CSSTATS", command=self.import_stats).grid(row=2, column=1, sticky="e", pady=(5, 12))
        self.import_status = ttk.Label(form, text="La importación solo realiza una petición HTTP normal; no evita verificaciones de seguridad.")
        self.import_status.grid(row=3, column=1, sticky="w", pady=(0, 8))
        self.profile_stats = self.text_field(form, "Datos del perfil importados (sin fecha)", 4, 3)
        self.day_fields: list[dict[str, tk.Widget]] = []
        days_frame = ttk.Frame(form)
        days_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        days_frame.configure(height=220)
        days_frame.grid_propagate(False)
        canvas = tk.Canvas(days_frame, bg="#101316", highlightthickness=0)
        scrollbar = ttk.Scrollbar(days_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(inner_window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for number, day_name in enumerate(("LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO")):
            group = ttk.LabelFrame(inner, text=day_name, padding=10)
            group.pack(fill="x", expand=True, pady=5)
            title = ttk.Entry(group)
            title.pack(fill="x", pady=(0, 5))
            title.insert(0, "Entrenamiento" if number < 5 else "Partidas / descanso")
            stats = tk.Text(group, height=2, wrap="word", bg="#20272c", fg="#e7e8e4", insertbackground="#e7e8e4", relief="flat", padx=8, pady=5)
            stats.pack(fill="x", pady=(0, 5))
            notes = tk.Text(group, height=2, wrap="word", bg="#20272c", fg="#e7e8e4", insertbackground="#e7e8e4", relief="flat", padx=8, pady=5)
            notes.pack(fill="x")
            self.day_fields.append({"title": title, "stats": stats, "notes": notes})
        self.week_focus = self.field(form, "Objetivo de la semana", 6)
        self.week_summary = self.text_field(form, "Resumen / mejoras", 7, 3)
        ttk.Button(form, text="GENERAR INFORME SEMANAL", command=self.generate_week).grid(row=8, column=1, sticky="e", pady=(12, 0))
        form.rowconfigure(5, weight=1)

    @staticmethod
    def monday_of_current_week() -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())

    def import_stats(self) -> None:
        url = self.profile_url.get().strip()
        self.import_status.configure(text="Conectando con CSStats…")
        self.update_idletasks()
        try:
            rows = fetch_profile(url)
        except (OSError, ValueError) as error:
            messagebox.showwarning(
                "No se han podido importar las estadísticas",
                f"{error}\n\nRevisa el perfil aquí y completa las estadísticas por día:\n{url}",
            )
            self.import_status.configure(text="Importación no disponible. Revisa el enlace y completa los días manualmente.")
            return
        joined = "\n".join(rows)
        self.profile_stats.insert("end", ("\n" if self.read_text(self.profile_stats) else "") + joined)
        self.import_status.configure(text="Datos de perfil encontrados. No se asignan a días para evitar alterar las fechas.")
        messagebox.showinfo(
            "Datos encontrados",
            "Se encontraron datos estáticos y se guardaron como datos generales del perfil.\n"
            "No se asignan a días porque la página no indica aquí la fecha de cada dato. Registra las estadísticas diarias abajo; las secciones cargadas por JavaScript pueden no estar incluidas.",
        )

    def generate_week(self) -> None:
        days = [
            {
                "title": str(entry["title"].get()),
                "stats": self.read_text(entry["stats"]),  # type: ignore[arg-type]
                "notes": self.read_text(entry["notes"]),  # type: ignore[arg-type]
            }
            for entry in self.day_fields
        ]
        data = {
            "profile_url": self.profile_url.get().strip(),
            "week_start": self.week_start.get().strip(),
            "profile_stats": self.read_text(self.profile_stats),
            "focus": self.week_focus.get().strip(),
            "summary": self.read_text(self.week_summary),
        }
        try:
            output = write_week(data, days)
        except (OSError, ValueError) as error:
            messagebox.showerror("No se pudo generar el informe", str(error))
            return
        messagebox.showinfo("Informe generado", f"Página semanal creada y añadida al índice:\n{output}")


if __name__ == "__main__":
    GeneratorApp().mainloop()
