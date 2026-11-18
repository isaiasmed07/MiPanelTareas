import os
import sqlite3
import ctypes
import tkinter as tk
from datetime import datetime, timedelta
from windows_toasts import Toast, WindowsToaster
import pystray
from PIL import Image, ImageDraw

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
# Ruta fija junto al script (al arrancar con Windows la carpeta de trabajo es otra)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tareas.db")

ANCHO, ALTO = 340, 540

# Paleta
BG = "#151917"
SURFACE = "#1D2320"
HOVER = "#252C28"
BORDER = "#2C3430"
TEXT = "#E8EDEA"
MUTED = "#8C9891"
SUBTLE = "#5D6862"
ACCENT = "#9FD1AA"
ACCENT_HOVER = "#B6DEBF"
ON_ACCENT = "#132017"
DANGER = "#E8907C"
PRIORIDAD_COLOR = {"Alta": "#E8907C", "Media": "#E3C07E", "Baja": "#86B6D6"}

# Tipografía e iconos de Windows 11
FUENTE = "Segoe UI Variable Text"
FUENTE_TITULO = "Segoe UI Variable Display"
ICONOS = "Segoe Fluent Icons"
IC_ADD = ""
IC_CLOSE = ""
IC_CIRCLE = ""
IC_DONE = ""
IC_DELETE = ""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

toaster = WindowsToaster("Mi Panel de Tareas")

# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────
db = sqlite3.connect(DB)
db.execute("""
CREATE TABLE IF NOT EXISTS tareas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    fecha TEXT NOT NULL,
    prioridad TEXT DEFAULT 'Media',
    completada INTEGER DEFAULT 0,
    notificada INTEGER DEFAULT 0
)
""")
db.execute("CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT)")
db.commit()

def leer_config(clave, defecto=None):
    fila = db.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
    return fila[0] if fila else defecto

def guardar_config(clave, valor):
    db.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", (clave, valor))
    db.commit()

# ─────────────────────────────────────────────
# UTILIDADES DE FECHA
# ─────────────────────────────────────────────
def fecha_larga():
    n = datetime.now()
    return f"{DIAS[n.weekday()].capitalize()}, {n.day} de {MESES_LARGO[n.month - 1]}"

def formato_fecha(fecha):
    """Devuelve ('Hoy, 14:30', vencida)."""
    try:
        dt = datetime.strptime(fecha, "%Y-%m-%d %H:%M")
    except ValueError:
        return fecha, False
    hoy = datetime.now().date()
    d = dt.date()
    if d == hoy:
        dia = "Hoy"
    elif d == hoy + timedelta(days=1):
        dia = "Mañana"
    elif d == hoy - timedelta(days=1):
        dia = "Ayer"
    else:
        dia = f"{d.day} {MESES[d.month - 1]}"
        if d.year != hoy.year:
            dia += f" {d.year}"
    return f"{dia}, {dt:%H:%M}", dt < datetime.now()

# ─────────────────────────────────────────────
# VENTANA
# ─────────────────────────────────────────────
root = tk.Tk()
root.title("Mis tareas")
root.configure(bg=BG)
root.overrideredirect(True)

user32 = ctypes.windll.user32
user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_void_p
user32.FindWindowW.restype = ctypes.c_void_p
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

def posicion_inicial():
    # Área de todos los monitores, para no aparecer fuera de pantalla
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    try:
        x, y = map(int, leer_config("posicion", "").lstrip("+").split("+"))
    except ValueError:
        x, y = vx + vw - ANCHO - 60, vy + 80
    x = max(vx, min(x, vx + vw - ANCHO))
    y = max(vy, min(y, vy + vh - ALTO))
    return x, y

px, py = posicion_inicial()
root.geometry(f"{ANCHO}x{ALTO}+{px}+{py}")

# ─────────────────────────────────────────────
# FIJAR AL ESCRITORIO (Windows)
# ─────────────────────────────────────────────
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010

def hwnd_ventana():
    return int(root.wm_frame(), 16)

def enviar_al_fondo():
    user32.SetWindowPos(hwnd_ventana(), HWND_BOTTOM, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

def colorref(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return r | (g << 8) | (b << 16)

def estilo_windows11(hwnd):
    # Esquinas redondeadas y borde sutil (solo Windows 11)
    try:
        dwm = ctypes.windll.dwmapi
        esquinas = ctypes.c_int(2)                 # DWMWCP_ROUND
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33,
                                  ctypes.byref(esquinas), ctypes.sizeof(esquinas))
        borde = ctypes.c_uint(colorref(BORDER))    # DWMWA_BORDER_COLOR
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 34,
                                  ctypes.byref(borde), ctypes.sizeof(borde))
    except Exception:
        pass

def fijar_al_escritorio():
    root.update_idletasks()
    hwnd = hwnd_ventana()

    # El escritorio pasa a ser el "dueño": la ventana sobrevive a Win+D
    progman = user32.FindWindowW("Progman", None)
    if progman:
        user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, progman)

    # Ocultar de la barra de tareas y de Alt+Tab
    estilo = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) or 0
    estilo = (estilo | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, estilo)

    estilo_windows11(hwnd)
    enviar_al_fondo()

def al_activarse(event):
    # Si haces clic en el widget, vuelve al fondo para no tapar otras ventanas
    if event.widget is root:
        root.after(150, enviar_al_fondo)

root.bind("<FocusIn>", al_activarse)

# ─────────────────────────────────────────────
# MOSTRAR / OCULTAR / SALIR
# ─────────────────────────────────────────────
def cerrar():
    root.withdraw()

def mostrar():
    root.deiconify()
    root.after(50, fijar_al_escritorio)

def alternar():
    if root.state() == "withdrawn":
        mostrar()
    else:
        cerrar()

def salir():
    icono.stop()
    db.close()
    root.destroy()

# ─────────────────────────────────────────────
# ICONO EN LA BANDEJA DEL SISTEMA
# ─────────────────────────────────────────────
def crear_imagen_icono():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=16, fill=ACCENT)
    d.line((19, 33, 28, 42, 45, 23), fill=BG, width=7, joint="curve")
    return img

# pystray corre en otro hilo: las acciones se pasan a tkinter con root.after
icono = pystray.Icon(
    "MiPanelTareas",
    crear_imagen_icono(),
    "Mis tareas",
    menu=pystray.Menu(
        pystray.MenuItem("Mostrar / ocultar",
                         lambda: root.after(0, alternar), default=True),
        pystray.MenuItem("Salir", lambda: root.after(0, salir)),
    ),
)

# ─────────────────────────────────────────────
# COMPONENTES
# ─────────────────────────────────────────────
def boton(parent, texto, comando, fg=MUTED, hover=TEXT,
          fuente=(ICONOS, 10), bg=None, hover_bg=None, **kw):
    """Botón plano hecho con un Label (control total del estilo)."""
    bg = bg or parent.cget("bg")
    lbl = tk.Label(parent, text=texto, fg=fg, bg=bg, font=fuente, cursor="hand2", **kw)
    lbl.fg_base = fg

    def entrar(_):
        lbl.config(fg=hover)
        if hover_bg:
            lbl.config(bg=hover_bg)

    def salir_(_):
        lbl.config(fg=lbl.fg_base)
        if hover_bg:
            lbl.config(bg=bg)

    lbl.bind("<Enter>", entrar)
    lbl.bind("<Leave>", salir_)
    if comando:
        lbl.bind("<Button-1>", lambda e: comando())
    return lbl

def pintar(widget, color):
    try:
        widget.config(bg=color)
    except tk.TclError:
        pass
    for hijo in widget.winfo_children():
        pintar(hijo, color)

def descendientes(widget):
    yield widget
    for hijo in widget.winfo_children():
        yield from descendientes(hijo)

def contiene_puntero(widget):
    x, y = widget.winfo_pointerxy()
    w = widget.winfo_containing(x, y)
    while w is not None:
        if w is widget:
            return True
        w = w.master
    return False

def entrada(parent, valor="", **kw):
    e = tk.Entry(
        parent, font=(FUENTE, 10), bg=SURFACE, fg=TEXT,
        insertbackground=TEXT, relief="flat", bd=0,
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        **kw
    )
    e.insert(0, valor)
    return e

# ─────────────────────────────────────────────
# ENCABEZADO
# ─────────────────────────────────────────────
def mover_inicio(event):
    root._drag = (event.x_root - root.winfo_x(), event.y_root - root.winfo_y())

def mover_ventana(event):
    dx, dy = root._drag
    root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

def mover_fin(_):
    guardar_config("posicion", f"+{root.winfo_x()}+{root.winfo_y()}")

header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=20, pady=(18, 0))

izq = tk.Frame(header, bg=BG)
izq.pack(side="left")

tk.Label(izq, text="Tareas", font=(FUENTE_TITULO, 20, "bold"),
         fg=TEXT, bg=BG).pack(anchor="w")
lbl_fecha = tk.Label(izq, text=fecha_larga(), font=(FUENTE, 9), fg=MUTED, bg=BG)
lbl_fecha.pack(anchor="w")

for w in descendientes(header):
    w.bind("<Button-1>", mover_inicio)
    w.bind("<B1-Motion>", mover_ventana)
    w.bind("<ButtonRelease-1>", mover_fin)

der = tk.Frame(header, bg=BG)
der.pack(side="right", anchor="n", pady=(8, 0))

boton(der, IC_CLOSE, cerrar, fg=SUBTLE, hover=TEXT,
      fuente=(ICONOS, 9)).pack(side="right", padx=(14, 0), pady=6)
boton(der, IC_ADD, lambda: abrir_formulario(), fg=ON_ACCENT, hover=ON_ACCENT,
      bg=ACCENT, hover_bg=ACCENT_HOVER, fuente=(ICONOS, 10),
      padx=9, pady=6).pack(side="right")

# ─────────────────────────────────────────────
# PESTAÑAS
# ─────────────────────────────────────────────
tabs = tk.Frame(root, bg=BG)
tabs.pack(fill="x", padx=20, pady=(20, 0))
tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=20)

modo = "pendientes"

def cambiar_modo(nuevo):
    global modo
    modo = nuevo
    actualizar()

def dibujar_tabs(n_pend, n_hist):
    for w in tabs.winfo_children():
        w.destroy()

    for texto, valor, n in (("Pendientes", "pendientes", n_pend),
                            ("Historial", "historial", n_hist)):
        activo = modo == valor
        tab = tk.Frame(tabs, bg=BG, cursor="hand2")
        tab.pack(side="left", padx=(0, 22))

        fila = tk.Frame(tab, bg=BG)
        fila.pack()
        tk.Label(fila, text=texto, bg=BG,
                 font=(FUENTE, 10, "bold" if activo else "normal"),
                 fg=TEXT if activo else MUTED).pack(side="left")
        if n:
            tk.Label(fila, text=str(n), bg=BG, font=(FUENTE, 8),
                     fg=ACCENT if activo else SUBTLE).pack(side="left", padx=(6, 0))

        tk.Frame(tab, bg=ACCENT if activo else BG, height=2).pack(fill="x", pady=(9, 0))

        for w in descendientes(tab):
            w.config(cursor="hand2")
            w.bind("<Button-1>", lambda e, v=valor: cambiar_modo(v))

# ─────────────────────────────────────────────
# CUERPO: LISTA CON SCROLL + FORMULARIO
# ─────────────────────────────────────────────
cuerpo = tk.Frame(root, bg=BG)
cuerpo.pack(fill="both", expand=True)

canvas = tk.Canvas(cuerpo, bg=BG, highlightthickness=0, bd=0, yscrollincrement=20)
lista = tk.Frame(canvas, bg=BG)
ventana_lista = canvas.create_window((0, 0), window=lista, anchor="nw")
lista.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", lambda e: canvas.itemconfig(ventana_lista, width=e.width))

def rueda(event):
    if canvas.winfo_ismapped() and lista.winfo_height() > canvas.winfo_height():
        canvas.yview_scroll(int(-event.delta / 120), "units")

root.bind_all("<MouseWheel>", rueda)

formulario = tk.Frame(cuerpo, bg=BG)

# ─────────────────────────────────────────────
# ACCIONES SOBRE TAREAS
# ─────────────────────────────────────────────
def completar(task_id):
    db.execute("UPDATE tareas SET completada=1 WHERE id=?", (task_id,))
    db.commit()
    actualizar()

def restaurar(task_id):
    db.execute("UPDATE tareas SET completada=0 WHERE id=?", (task_id,))
    db.commit()
    actualizar()

def eliminar(task_id):
    db.execute("DELETE FROM tareas WHERE id=?", (task_id,))
    db.commit()
    actualizar()

# ─────────────────────────────────────────────
# TARJETA DE TAREA
# ─────────────────────────────────────────────
def tarjeta(task_id, titulo_t, desc, fecha, prioridad_t):
    pendiente = modo == "pendientes"

    card = tk.Frame(lista, bg=SURFACE, padx=12, pady=11)
    card.pack(fill="x", padx=16, pady=4)
    card.columnconfigure(1, weight=1)

    # Círculo para completar / restaurar
    def click_check():
        if pendiente:
            check.config(text=IC_DONE, fg=ACCENT)
            root.after(280, lambda: completar(task_id))
        else:
            restaurar(task_id)

    check = boton(card, IC_CIRCLE if pendiente else IC_DONE, click_check,
                  fg=SUBTLE if pendiente else ACCENT,
                  hover=ACCENT if pendiente else MUTED,
                  fuente=(ICONOS, 13))
    check.grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 11))

    # Texto
    tk.Label(card, text=titulo_t, bg=SURFACE, anchor="w", justify="left",
             wraplength=205,
             font=(FUENTE, 10) if pendiente else (FUENTE, 10, "overstrike"),
             fg=TEXT if pendiente else MUTED).grid(row=0, column=1, sticky="w")

    if desc:
        tk.Label(card, text=desc, bg=SURFACE, anchor="w", justify="left",
                 wraplength=205, font=(FUENTE, 9),
                 fg=MUTED if pendiente else SUBTLE).grid(row=1, column=1, sticky="w", pady=(2, 0))

    meta = tk.Frame(card, bg=SURFACE)
    meta.grid(row=2, column=1, sticky="w", pady=(7, 0))

    texto_fecha, vencida = formato_fecha(fecha)
    vencida = vencida and pendiente
    tk.Label(meta, text=("Vencida · " if vencida else "") + texto_fecha,
             font=(FUENTE, 8), bg=SURFACE,
             fg=DANGER if vencida else MUTED).pack(side="left")
    tk.Label(meta, text="●", font=(FUENTE, 7), bg=SURFACE,
             fg=PRIORIDAD_COLOR.get(prioridad_t, MUTED)).pack(side="left", padx=(10, 4))
    tk.Label(meta, text=prioridad_t, font=(FUENTE, 8), bg=SURFACE,
             fg=MUTED).pack(side="left")

    # Eliminar: aparece al pasar el ratón; pide un segundo clic para confirmar
    confirmando = [False]

    def click_borrar():
        if confirmando[0]:
            eliminar(task_id)
        else:
            confirmando[0] = True
            borrar.config(text="¿Eliminar?", font=(FUENTE, 8), fg=DANGER)
            borrar.fg_base = DANGER

    borrar = boton(card, IC_DELETE, click_borrar, fg=SURFACE, hover=DANGER,
                   fuente=(ICONOS, 10))
    borrar.grid(row=0, column=2, sticky="ne", padx=(8, 0))

    # Efecto hover de la tarjeta
    def entrar(_):
        pintar(card, HOVER)
        if not confirmando[0]:
            borrar.fg_base = SUBTLE
            borrar.config(fg=SUBTLE if not contiene_puntero(borrar) else DANGER)

    def salir_(_):
        if contiene_puntero(card):
            return
        pintar(card, SURFACE)
        confirmando[0] = False
        borrar.fg_base = SURFACE
        borrar.config(text=IC_DELETE, font=(ICONOS, 10), fg=SURFACE)

    for w in descendientes(card):
        w.bind("<Enter>", entrar, add="+")
        w.bind("<Leave>", salir_, add="+")

def estado_vacio():
    caja = tk.Frame(lista, bg=BG)
    caja.pack(pady=70)
    tk.Label(caja, text=IC_DONE, font=(ICONOS, 28), fg=SUBTLE, bg=BG).pack()
    if modo == "pendientes":
        titulo, sub = "Todo al día", "Pulsa + para añadir una tarea"
    else:
        titulo, sub = "Sin historial", "Las tareas completadas aparecerán aquí"
    tk.Label(caja, text=titulo, font=(FUENTE, 11, "bold"), fg=MUTED, bg=BG).pack(pady=(12, 2))
    tk.Label(caja, text=sub, font=(FUENTE, 9), fg=SUBTLE, bg=BG).pack()

# ─────────────────────────────────────────────
# REFRESCAR LISTA
# ─────────────────────────────────────────────
def actualizar():
    formulario.pack_forget()
    canvas.pack(fill="both", expand=True, pady=(12, 0))

    n_pend = db.execute("SELECT COUNT(*) FROM tareas WHERE completada=0").fetchone()[0]
    n_hist = db.execute("SELECT COUNT(*) FROM tareas WHERE completada=1").fetchone()[0]
    dibujar_tabs(n_pend, n_hist)

    for w in lista.winfo_children():
        w.destroy()

    if modo == "pendientes":
        filas = db.execute(
            """SELECT id, titulo, descripcion, fecha, prioridad
            FROM tareas WHERE completada=0 ORDER BY fecha"""
        ).fetchall()
    else:
        filas = db.execute(
            """SELECT id, titulo, descripcion, fecha, prioridad
            FROM tareas WHERE completada=1 ORDER BY id DESC LIMIT 100"""
        ).fetchall()

    if not filas:
        estado_vacio()
    for fila in filas:
        tarjeta(*fila)

    tk.Frame(lista, bg=BG, height=14).pack()
    canvas.yview_moveto(0)

# ─────────────────────────────────────────────
# FORMULARIO "NUEVA TAREA" (dentro del widget)
# ─────────────────────────────────────────────
def abrir_formulario():
    for w in formulario.winfo_children():
        w.destroy()
    canvas.pack_forget()
    formulario.pack(fill="both", expand=True, padx=20, pady=(18, 0))

    def etiqueta(texto):
        tk.Label(formulario, text=texto, font=(FUENTE, 8), fg=MUTED,
                 bg=BG).pack(anchor="w", pady=(12, 4))

    tk.Label(formulario, text="Nueva tarea", font=(FUENTE_TITULO, 13, "bold"),
             fg=TEXT, bg=BG).pack(anchor="w")

    etiqueta("Título")
    e_titulo = entrada(formulario)
    e_titulo.pack(fill="x", ipady=7, ipadx=6)

    etiqueta("Descripción (opcional)")
    e_desc = entrada(formulario)
    e_desc.pack(fill="x", ipady=7, ipadx=6)

    # Fecha y hora: por defecto, la próxima hora en punto
    sugerida = (datetime.now() + timedelta(hours=1)).replace(minute=0)
    etiqueta("Fecha y hora")
    fila = tk.Frame(formulario, bg=BG)
    fila.pack(fill="x")
    e_dia = entrada(fila, sugerida.strftime("%Y-%m-%d"), width=11)
    e_dia.pack(side="left", ipady=7, ipadx=6)
    e_hora = entrada(fila, sugerida.strftime("%H:%M"), width=6)
    e_hora.pack(side="left", padx=(8, 0), ipady=7, ipadx=6)

    def poner_dia(dias):
        e_dia.delete(0, "end")
        e_dia.insert(0, (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d"))

    boton(fila, "Mañana", lambda: poner_dia(1), fuente=(FUENTE, 9),
          fg=MUTED, hover=ACCENT).pack(side="right")
    boton(fila, "Hoy", lambda: poner_dia(0), fuente=(FUENTE, 9),
          fg=MUTED, hover=ACCENT).pack(side="right", padx=(0, 12))

    # Prioridad como "pastillas" seleccionables
    etiqueta("Prioridad")
    prioridad = tk.StringVar(value="Media")
    pastillas = tk.Frame(formulario, bg=BG)
    pastillas.pack(fill="x")
    etiquetas_prio = {}

    def pintar_pastillas():
        for nombre, lbl in etiquetas_prio.items():
            sel = prioridad.get() == nombre
            lbl.config(fg=TEXT if sel else MUTED,
                       bg=HOVER if sel else SURFACE,
                       highlightbackground=PRIORIDAD_COLOR[nombre] if sel else BORDER)

    for i, nombre in enumerate(("Alta", "Media", "Baja")):
        lbl = tk.Label(pastillas, text=nombre, font=(FUENTE, 9), cursor="hand2",
                       highlightthickness=1, pady=6)
        lbl.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 6, 0))
        lbl.bind("<Button-1>", lambda e, n=nombre: (prioridad.set(n), pintar_pastillas()))
        etiquetas_prio[nombre] = lbl
    pintar_pastillas()

    error = tk.Label(formulario, text="", font=(FUENTE, 8), fg=DANGER, bg=BG)
    error.pack(anchor="w", pady=(12, 0))

    def guardar():
        t = e_titulo.get().strip()
        d = e_desc.get().strip()
        f = f"{e_dia.get().strip()} {e_hora.get().strip()}"

        if not t:
            error.config(text="Escribe un título.")
            e_titulo.focus_set()
            return
        try:
            f = datetime.strptime(f, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
        except ValueError:
            error.config(text="Fecha AAAA-MM-DD y hora HH:MM, por favor.")
            return

        db.execute(
            "INSERT INTO tareas (titulo, descripcion, fecha, prioridad) VALUES (?, ?, ?, ?)",
            (t, d, f, prioridad.get())
        )
        db.commit()
        cambiar_modo("pendientes")

    # Botones
    acciones = tk.Frame(formulario, bg=BG)
    acciones.pack(fill="x", side="bottom", pady=(0, 20))
    boton(acciones, "Guardar", guardar, fg=ON_ACCENT, hover=ON_ACCENT,
          bg=ACCENT, hover_bg=ACCENT_HOVER, fuente=(FUENTE, 10, "bold"),
          padx=18, pady=7).pack(side="right")
    boton(acciones, "Cancelar", actualizar, fuente=(FUENTE, 10),
          fg=MUTED, hover=TEXT, padx=12, pady=7).pack(side="right", padx=(0, 6))

    for e in (e_titulo, e_desc, e_dia, e_hora):
        e.bind("<Return>", lambda ev: guardar())
        e.bind("<Escape>", lambda ev: actualizar())

    root.after(50, e_titulo.focus_force)

# ─────────────────────────────────────────────
# RECORDATORIOS
# ─────────────────────────────────────────────
def revisar_recordatorios():
    lbl_fecha.config(text=fecha_larga())
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    filas = db.execute(
        """SELECT id, titulo, fecha FROM tareas
        WHERE completada=0 AND notificada=0 AND fecha<=?""",
        (ahora,)
    ).fetchall()

    for task_id, titulo_t, fecha in filas:
        try:
            toast = Toast()
            toast.text_fields = [
                "Recordatorio de tarea",
                titulo_t,
                "Fecha programada: " + fecha
            ]
            toaster.show_toast(toast)
            db.execute("UPDATE tareas SET notificada=1 WHERE id=?", (task_id,))
            db.commit()
        except Exception as err:
            print("Error de notificación:", err)

    root.after(15000, revisar_recordatorios)

# ─────────────────────────────────────────────
# INICIO
# ─────────────────────────────────────────────
actualizar()
root.after(100, fijar_al_escritorio)
icono.run_detached()
revisar_recordatorios()
root.mainloop()
