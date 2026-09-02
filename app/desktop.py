from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import traceback
from datetime import date
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:  # pragma: no cover - only on broken Python installations
    raise RuntimeError('SENDA.V0 Desktop requiere el toolkit nativo Tk incluido con Python para Windows.') from exc

from .desktop_model import (
    ALARMS, DISTRICTS, MONTHS, MOVEMENT_CATEGORIES, PAGE_SIZES, QUARTERS,
    available_years, create_context, export_movements, filters_from_values, import_files, export_sync_database,
    alarm_visual, information_alarm_row,
)

APP_TITLE = 'SENDA.V0 0.4.2 · Escritorio'
BG = '#eef2f6'
NAVY = '#15314b'
GOLD = '#cfa43a'
MUTED = '#65758b'
WHITE = '#ffffff'
BLUE = '#0b6fc2'
BLUE_DARK = '#0a4777'
PANEL = '#f8fbfe'
BORDER = '#d6e2ec'
ALARM_RED = '#dc2626'
ALARM_YELLOW = '#eab308'
ALARM_GREEN = '#16a34a'
CHART_COLORS = ('#0b6fc2','#2563eb','#7c3aed','#0f766e','#ea580c','#be123c','#64748b','#0891b2')

# Escala tipográfica: lectura cómoda sin perder densidad en pantallas de oficina.
BODY_FONT_SIZE = 12
PANEL_TITLE_SIZE = 14
SECTION_TITLE_SIZE = 23
NAV_FONT_SIZE = 13
KPI_VALUE_SIZE = 24
KPI_LABEL_SIZE = 12
SMALL_FONT_SIZE = 11


def _safe_text(value):
    return '' if value is None else str(value)


def _rounded_rect(canvas, x1, y1, x2, y2, radius=14, **kwargs):
    radius = max(2, min(radius, (x2-x1)//2, (y2-y1)//2))
    points = [x1+radius,y1, x2-radius,y1, x2,y1, x2,y1+radius,
              x2,y2-radius, x2,y2, x2-radius,y2, x1+radius,y2,
              x1,y2, x1,y2-radius, x1,y1+radius, x1,y1]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class RoundedButton(tk.Canvas):
    """Botón Canvas con esquinas redondeadas y estado disabled compatible con Tk."""
    def __init__(self,parent,text,command=None,*,fill=WHITE,fg=NAVY,hover_fill='#edf3f8',outline=BORDER,canvas_bg=None,height=38,width=None,font_size=None,bold=True,state='normal'):
        self.text=text;self.command=command;self.fill=fill;self.fg=fg;self.hover_fill=hover_fill;self.outline=outline;self._state=state;self._hover=False
        self.font_size=font_size or BODY_FONT_SIZE;self.bold=bold
        auto_width=max(92,int(len(str(text))*self.font_size*.68)+34)
        try: parent_bg=parent.cget('background')
        except Exception: parent_bg=BG
        super().__init__(parent,width=width or auto_width,height=height,bg=canvas_bg or parent_bg or BG,highlightthickness=0,bd=0,cursor=('hand2' if state!='disabled' else 'arrow'))
        self.bind('<Configure>',lambda e:self._draw());self.bind('<Enter>',self._enter);self.bind('<Leave>',self._leave);self.bind('<Button-1>',self._click)
        self._draw()
    def _enter(self,event=None):
        if self._state!='disabled':self._hover=True;self._draw()
    def _leave(self,event=None):self._hover=False;self._draw()
    def _click(self,event=None):
        if self._state!='disabled' and self.command:self.command()
    def _draw(self):
        self.delete('all');w=max(20,self.winfo_width());h=max(20,self.winfo_height())
        if self._state=='disabled':fill='#e5e7eb';fg='#94a3b8';outline='#d1d5db'
        else:fill=self.hover_fill if self._hover else self.fill;fg=self.fg;outline=self.outline
        _rounded_rect(self,2,2,w-2,h-2,10,fill=fill,outline=outline,width=1)
        self.create_text(w/2,h/2,text=self.text,fill=fg,font=('Segoe UI',self.font_size,'bold' if self.bold else 'normal'))
    def configure(self,cnf=None,**kwargs):
        if cnf:kwargs.update(cnf)
        handled=False
        for key in ('state','text','command'):
            if key in kwargs:
                handled=True;val=kwargs.pop(key)
                if key=='state':self._state=str(val);super().configure(cursor=('arrow' if self._state=='disabled' else 'hand2'))
                elif key=='text':self.text=str(val)
                else:self.command=val
        if kwargs:super().configure(**kwargs)
        if handled:self._draw()
        return None
    config=configure


class KpiCard(tk.Canvas):
    """Tarjeta compacta de KPI dibujada en Canvas para evitar el aspecto cuadrado de ttk."""
    def __init__(self, parent, label, accent=BLUE, **kwargs):
        super().__init__(parent, height=72, bg=BG, highlightthickness=0, bd=0, **kwargs)
        self.label = label
        self.accent = accent
        self.value = '0'
        self.bind('<Configure>', lambda e: self._draw())

    def set(self, value):
        self.value = str(value)
        self._draw()

    def _draw(self):
        w=max(90,self.winfo_width()); h=max(68,self.winfo_height())
        self.delete('all')
        _rounded_rect(self, 3, 3, w-3, h-4, 14, fill=WHITE, outline=BORDER, width=1)
        _rounded_rect(self, 4, 4, 10, h-5, 4, fill=self.accent, outline=self.accent)
        self.create_text(20, 24, anchor='w', text=self.value, fill=NAVY, font=('Segoe UI',KPI_VALUE_SIZE,'bold'))
        self.create_text(20, 50, anchor='w', text=self.label, fill=MUTED, font=('Segoe UI',KPI_LABEL_SIZE,'bold'))


class HorizontalBarChart(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=WHITE, highlightthickness=0, bd=0, **kwargs)
        self.data=[]
        self.bind('<Configure>', lambda e:self._draw())

    def set_data(self, mapping, max_items=8):
        self.data=list(mapping.items())[:max_items]
        self._draw()

    def _draw(self):
        self.delete('all'); w=max(180,self.winfo_width()); h=max(120,self.winfo_height())
        if not self.data:
            self.create_text(w/2,h/2,text='Sin datos para el filtro seleccionado',fill=MUTED,font=('Segoe UI',BODY_FONT_SIZE))
            return
        maxv=max(v for _,v in self.data) or 1
        top=8; row=max(20,(h-16)//max(1,len(self.data)))
        label_w=min(145,max(90,int(w*.34)))
        for i,(label,value) in enumerate(self.data):
            y=top+i*row
            self.create_text(6,y+row/2,anchor='w',text=str(label)[:22],fill=NAVY,font=('Segoe UI',SMALL_FONT_SIZE,'bold'))
            x1=label_w; x2=w-48; barw=max(2,(x2-x1)*(value/maxv))
            self.create_rectangle(x1,y+5,x2,y+row-6,fill='#edf3f8',outline='')
            self.create_rectangle(x1,y+5,x1+barw,y+row-6,fill=CHART_COLORS[i%len(CHART_COLORS)],outline='')
            self.create_text(w-7,y+row/2,anchor='e',text=f'{value:,}'.replace(',','.'),fill=NAVY,font=('Segoe UI',SMALL_FONT_SIZE,'bold'))


class MonthlyLineChart(tk.Canvas):
    def __init__(self,parent,**kwargs):
        super().__init__(parent,bg=WHITE,highlightthickness=0,bd=0,**kwargs)
        self.data={}
        self.bind('<Configure>',lambda e:self._draw())
    def set_data(self,mapping): self.data=dict(mapping); self._draw()
    def _draw(self):
        self.delete('all');w=max(200,self.winfo_width());h=max(120,self.winfo_height())
        vals=[int(self.data.get(m,0)) for m in range(1,13)]
        if not any(vals):
            self.create_text(w/2,h/2,text='Sin movimientos mensuales',fill=MUTED,font=('Segoe UI',BODY_FONT_SIZE));return
        left,right,top,bottom=28,w-12,12,h-28;maxv=max(vals) or 1
        self.create_line(left,bottom,right,bottom,fill=BORDER)
        pts=[]
        for idx,val in enumerate(vals):
            x=left+(right-left)*(idx/11); y=bottom-(bottom-top)*(val/maxv);pts.extend((x,y))
            self.create_oval(x-3,y-3,x+3,y+3,fill=BLUE,outline=WHITE,width=1)
            self.create_text(x,bottom+13,text=str(idx+1),fill=MUTED,font=('Segoe UI',SMALL_FONT_SIZE))
        if len(pts)>=4:self.create_line(*pts,fill=BLUE,width=2,smooth=True)
        self.create_text(left,top,anchor='w',text=f'Máx. {maxv:,}'.replace(',','.'),fill=MUTED,font=('Segoe UI',SMALL_FONT_SIZE))


class SendaDesktop(tk.Tk):
    def __init__(self, data_dir=None):
        super().__init__()
        self.ctx = create_context(data_dir)
        self.title(APP_TITLE)
        self.geometry('1440x860')
        self.minsize(1220, 740)
        self.configure(bg=BG)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._jobs = queue.Queue()
        self._selected_information = set()
        self._active_control_id = None
        self._info_offset = 0
        self._movement_offset = 0
        self._current_entity = None
        self._configure_style()
        self._set_icon()
        self._build_shell()
        self.after(100, self._drain_jobs)
        self.refresh_all()

    def _set_icon(self):
        root = Path(__file__).resolve().parents[1]
        ico = root / 'assets' / 'senda_v0.ico'
        try:
            if ico.exists(): self.iconbitmap(default=str(ico))
        except Exception:
            pass

    def _configure_style(self):
        style = ttk.Style(self)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('TFrame', background=BG)
        style.configure('Card.TFrame', background=WHITE, relief='solid', borderwidth=1)
        style.configure('Header.TLabel', background=NAVY, foreground=WHITE, font=('Segoe UI', NAV_FONT_SIZE, 'bold'))
        style.configure('Title.TLabel', background=BG, foreground=NAVY, font=('Segoe UI', SECTION_TITLE_SIZE, 'bold'))
        style.configure('KpiValue.TLabel', background=WHITE, foreground=NAVY, font=('Segoe UI', KPI_VALUE_SIZE, 'bold'))
        style.configure('KpiLabel.TLabel', background=WHITE, foreground=MUTED, font=('Segoe UI', KPI_LABEL_SIZE, 'bold'))
        style.configure('Gold.TButton', font=('Segoe UI', BODY_FONT_SIZE, 'bold'))
        style.configure('Treeview', rowheight=37, font=('Segoe UI', BODY_FONT_SIZE))
        style.configure('Treeview.Heading', font=('Segoe UI', BODY_FONT_SIZE, 'bold'))
        style.configure('TNotebook.Tab', padding=(20, 10), font=('Segoe UI', NAV_FONT_SIZE, 'bold'))
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', WHITE), ('!selected', '#dbe7f1')], foreground=[('selected', BLUE_DARK), ('!selected', NAVY)])
        style.configure('TLabel', background=BG, foreground=NAVY, font=('Segoe UI', BODY_FONT_SIZE))
        style.configure('TButton', font=('Segoe UI', BODY_FONT_SIZE, 'bold'), padding=(9, 5))
        style.configure('TCombobox', padding=4, font=('Segoe UI', BODY_FONT_SIZE))
        style.configure('TEntry', padding=5, font=('Segoe UI', BODY_FONT_SIZE))

    def _build_shell(self):
        header = tk.Frame(self, bg=NAVY, height=62)
        header.pack(fill='x')
        tk.Label(header, text='SENDA.V0', bg=NAVY, fg=WHITE, font=('Segoe UI', SECTION_TITLE_SIZE, 'bold')).pack(side='left', padx=(18,8), pady=13)
        tk.Label(header, text='Gestión registral local · Escritorio', bg=NAVY, fg='#cbd5df', font=('Segoe UI', BODY_FONT_SIZE)).pack(side='left', pady=17)
        self.connection_badge = tk.Label(header, text='● LOCAL · OFFLINE', bg=NAVY, fg='#7dd3a7', font=('Segoe UI', BODY_FONT_SIZE, 'bold'))
        self.connection_badge.pack(side='right', padx=(10,18))
        self.github_update_button = RoundedButton(
            header, text='↻ ACTUALIZAR DESDE GITHUB', command=self._update_from_github,
            fill='#16834f', fg=WHITE, hover_fill='#116b41', outline='#16834f', canvas_bg=NAVY, height=40
        )
        self.github_update_button.pack(side='right', padx=(8,0), pady=11)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(10,12))
        self.tab_home = ttk.Frame(self.notebook)
        self.tab_info = ttk.Frame(self.notebook)
        self.tab_control = ttk.Frame(self.notebook)
        self.tab_management = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_home, text='INICIO')
        self.notebook.add(self.tab_info, text='INFORMACIÓN SENDA')
        self.notebook.add(self.tab_control, text='CONTROL')
        self.notebook.add(self.tab_management, text='GESTIÓN')
        self.notebook.bind('<<NotebookTabChanged>>', lambda e: self.refresh_current_tab())
        self._build_home()
        self._build_information()
        self._build_control()
        self._build_management()

        self.status_var = tk.StringVar(value=f'Datos: {self.ctx.data_root}')
        tk.Label(self, textvariable=self.status_var, anchor='w', bg='#dfe6ed', fg=NAVY, font=('Segoe UI', BODY_FONT_SIZE)).pack(fill='x', side='bottom', ipady=5, padx=0)

    def _github_updater_script(self):
        if getattr(sys, 'frozen', False):
            roots = [Path(sys.executable).resolve().parent]
        else:
            roots = [Path(__file__).resolve().parents[1]]
        for root in roots:
            script = root / 'scripts' / 'install_from_github.ps1'
            if script.is_file():
                return script
        return None

    def _update_from_github(self):
        if os.name != 'nt':
            return messagebox.showinfo('SENDA.V0', 'La actualización automática desde GitHub está disponible en Windows.')
        script = self._github_updater_script()
        if script is None:
            return messagebox.showerror(
                'SENDA.V0',
                'No se encontró el actualizador de GitHub en esta instalación.\n\n'
                'Instale primero el paquete Desktop corregido desde la Release de GitHub.'
            )
        ok = messagebox.askyesno(
            'Actualizar SENDA.V0',
            'SENDA buscará la última versión publicada en GitHub.\n\n'
            'La aplicación se cerrará durante la actualización y volverá a abrirse al terminar.\n'
            'Los datos guardados en %LOCALAPPDATA%\\SENDA.V0 NO se borrarán.\n\n'
            '¿Desea continuar?'
        )
        if not ok:
            return
        try:
            flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            subprocess.Popen(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                cwd=str(script.parent.parent), creationflags=flags
            )
            self.status_var.set('Actualizador iniciado. SENDA se cerrará para instalar la última versión...')
            self.github_update_button.configure(state='disabled', text='ACTUALIZANDO...')
        except Exception as exc:
            messagebox.showerror('SENDA.V0', f'No fue posible iniciar la actualización desde GitHub.\n\n{exc}')

    def _filter_bar(self, parent, *, include_movement=True, callback=None):
        bar = ttk.Frame(parent)
        bar.pack(fill='x', pady=(0,8))
        values = {}
        def add(label, vals, width=14):
            ttk.Label(bar, text=label).pack(side='left', padx=(0,4))
            v = tk.StringVar(value=vals[0])
            c = ttk.Combobox(bar, textvariable=v, values=vals, width=width, state='readonly')
            c.pack(side='left', padx=(0,10))
            if callback: c.bind('<<ComboboxSelected>>', lambda e: callback())
            return v
        values['year'] = add('Año', ['TODOS'], 8)
        values['quarter'] = add('Trimestre', list(QUARTERS), 9)
        values['month'] = add('Mes', list(MONTHS), 7)
        values['district'] = add('Distrito', list(DISTRICTS), 20)
        values['alarm'] = add('Alarma', list(ALARMS), 9)
        if include_movement:
            values['movement'] = add('Movimiento', list(MOVEMENT_CATEGORIES), 17)
        ttk.Label(bar, text='Buscar').pack(side='left', padx=(0,4))
        values['search'] = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=values['search'], width=20)
        ent.pack(side='left', padx=(0,6))
        if callback:
            ent.bind('<Return>', lambda e: callback())
            RoundedButton(bar, text='Aplicar', command=callback).pack(side='left')
            RoundedButton(bar, text='Limpiar', command=lambda: self._clear_filter_values(values, callback)).pack(side='left', padx=4)
        return values

    def _clear_filter_values(self, values, callback):
        for k,v in values.items():
            v.set('TODOS' if k not in ('search',) else '')
        callback()

    def _filters(self, values):
        return filters_from_values(
            year=values['year'].get(), quarter=values['quarter'].get(), month=values['month'].get(),
            district=values['district'].get(), alarm=values['alarm'].get(),
            movement=values.get('movement', tk.StringVar(value='TODOS')).get(), search=values['search'].get())

    def _refresh_years(self, values):
        years = available_years(self.ctx.repo)
        for child in self.winfo_children():
            pass
        # Find the combobox bound to the same StringVar.
        def walk(widget):
            for c in widget.winfo_children():
                try:
                    if isinstance(c, ttk.Combobox) and str(c.cget('textvariable')) == str(values['year']):
                        c['values'] = years
                        if values['year'].get() not in years: values['year'].set('TODOS')
                        return True
                except Exception: pass
                if walk(c): return True
            return False
        walk(self)

    # -------------------- INICIO --------------------
    def _panel(self, parent, title):
        frame=tk.Frame(parent,bg=WHITE,highlightbackground=BORDER,highlightthickness=1,bd=0)
        head=tk.Frame(frame,bg=WHITE);head.pack(fill='x',padx=12,pady=(9,2))
        tk.Label(head,text=title,bg=WHITE,fg=NAVY,font=('Segoe UI',PANEL_TITLE_SIZE,'bold')).pack(side='left')
        return frame

    def _action_button(self,parent,text,command,primary=False):
        return RoundedButton(parent,text=text,command=command,fill=(BLUE if primary else WHITE),fg=(WHITE if primary else NAVY),
                             hover_fill=(BLUE_DARK if primary else '#edf3f8'),outline=(BLUE if primary else BORDER),height=38)

    def _build_home(self):
        top=tk.Frame(self.tab_home,bg=BG);top.pack(fill='x',pady=(1,6))
        tk.Label(top,text='Inicio',bg=BG,fg=NAVY,font=('Segoe UI',SECTION_TITLE_SIZE,'bold')).pack(side='left')
        self._action_button(top,'CARGAR DATOS',self._choose_import,True).pack(side='right',padx=(6,0))
        self._action_button(top,'EXCEL',lambda:self._export('xlsx')).pack(side='right',padx=3)
        self._action_button(top,'JSON',lambda:self._export('json')).pack(side='right',padx=3)
        self._action_button(top,'CSV',lambda:self._export('csv')).pack(side='right',padx=3)

        self.home_filters=self._filter_bar(self.tab_home,callback=self.refresh_home)

        self.kpi_frame=tk.Frame(self.tab_home,bg=BG);self.kpi_frame.pack(fill='x',pady=(0,7))
        self.kpi_cards={}
        specs=[('movimientos','MOVIMIENTOS',BLUE),('folios','FOLIOS / FINCAS','#2563eb'),
               ('tramites_pendientes','TRÁMITES PENDIENTES','#ca8a04'),('movimientos_tramite','MOV. CONTROL / GESTIÓN','#7c3aed'),
               ('casos_control','EN CONTROL','#0f766e'),('casos_gestion','EN GESTIÓN','#0891b2'),('alarmas_rojas','ALARMAS ROJAS',ALARM_RED)]
        for key,label,accent in specs:
            c=KpiCard(self.kpi_frame,label,accent=accent);c.pack(side='left',fill='x',expand=True,padx=(0,7));self.kpi_cards[key]=c

        body=tk.Frame(self.tab_home,bg=BG);body.pack(fill='both',expand=True)
        body.grid_columnconfigure(0,weight=1);body.grid_columnconfigure(1,weight=0,minsize=310);body.grid_rowconfigure(0,weight=1)
        main=tk.Frame(body,bg=BG);main.grid(row=0,column=0,sticky='nsew',padx=(0,8));main.grid_rowconfigure(0,weight=3);main.grid_rowconfigure(1,weight=2);main.grid_columnconfigure(0,weight=1)
        side=tk.Frame(body,bg=BG,width=310);side.grid(row=0,column=1,sticky='nsew');side.grid_propagate(False)

        charts=tk.Frame(main,bg=BG);charts.grid(row=0,column=0,sticky='nsew');
        for i in range(3):charts.grid_columnconfigure(i,weight=1)
        charts.grid_rowconfigure(0,weight=1)
        p1=self._panel(charts,'Movimientos por categoría');p1.grid(row=0,column=0,sticky='nsew',padx=(0,6));self.home_category_chart=HorizontalBarChart(p1,height=205);self.home_category_chart.pack(fill='both',expand=True,padx=8,pady=(2,8))
        p2=self._panel(charts,'Movimientos por distrito');p2.grid(row=0,column=1,sticky='nsew',padx=3);self.home_district_chart=HorizontalBarChart(p2,height=205);self.home_district_chart.pack(fill='both',expand=True,padx=8,pady=(2,8))
        p3=self._panel(charts,'Evolución mensual');p3.grid(row=0,column=2,sticky='nsew',padx=(6,0));self.home_month_chart=MonthlyLineChart(p3,height=205);self.home_month_chart.pack(fill='both',expand=True,padx=8,pady=(2,8))

        recent=self._panel(main,'Movimientos recientes');recent.grid(row=1,column=0,sticky='nsew',pady=(7,0))
        self.home_recent_tree=self._tree(recent,[('folio',115),('plano',110),('fecha',85),('movimiento',105),('codigo',65),('operacion',280),('distrito',125)],headings=('Folio','Plano','Fecha','Movimiento','Código','Operación','Distrito'))

        info=self._panel(side,'Información SENDA');info.pack(fill='x',pady=(0,7))
        self.home_info_var=tk.StringVar(value='Datos locales')
        tk.Label(info,textvariable=self.home_info_var,bg=WHITE,fg=MUTED,justify='left',anchor='w',font=('Segoe UI',SMALL_FONT_SIZE)).pack(fill='x',padx=12,pady=(3,10))

        alarms=self._panel(side,'🚨 Alarmas');alarms.pack(fill='x',pady=(0,7))
        self.alarm_vars={}
        for key,label,color,soft in [('red','90 días o más',ALARM_RED,'#fee2e2'),('yellow','Más de 60 días',ALARM_YELLOW,'#fef9c3'),('green','Hasta 60 días',ALARM_GREEN,'#dcfce7')]:
            row=tk.Frame(alarms,bg=soft,height=34);row.pack(fill='x',padx=9,pady=3);row.pack_propagate(False)
            tk.Frame(row,bg=color,width=5).pack(side='left',fill='y')
            tk.Label(row,text='●',bg=soft,fg=color,font=('Segoe UI',BODY_FONT_SIZE,'bold')).pack(side='left',padx=(8,4))
            tk.Label(row,text=label,bg=soft,fg=NAVY,font=('Segoe UI',SMALL_FONT_SIZE,'bold')).pack(side='left')
            v=tk.StringVar(value='0');self.alarm_vars[key]=v;tk.Label(row,textvariable=v,bg=soft,fg=NAVY,font=('Segoe UI',BODY_FONT_SIZE,'bold')).pack(side='right',padx=9)

        dist=self._panel(side,'Distritos');dist.pack(fill='both',expand=True)
        self.home_district_text=tk.Text(dist,height=9,wrap='word',bg=WHITE,fg=NAVY,relief='flat',font=('Segoe UI',BODY_FONT_SIZE),cursor='arrow')
        self.home_district_text.pack(fill='both',expand=True,padx=10,pady=(3,9))

    def refresh_home(self):
        self._refresh_years(self.home_filters)
        filters=self._filters(self.home_filters)
        data=self.ctx.repo.dashboard(filters)
        for k,c in self.kpi_cards.items():
            value=data.get(k,0) if k!='alarmas_rojas' else data.get('alarmas',{}).get('red',0)
            c.set(f"{int(value):,}".replace(',','.'))
        self.home_category_chart.set_data(data.get('por_categoria',{}),8)
        self.home_district_chart.set_data(data.get('por_distrito',{}),6)
        self.home_month_chart.set_data(data.get('por_mes',{}))
        a=data.get('alarmas',{})
        for k,v in self.alarm_vars.items():v.set(f"{int(a.get(k,0)):,}".replace(',','.'))
        self.home_info_var.set(f"Datos locales\n{self.ctx.data_root}\n\nFiltro activo: {filters or 'Todos los datos'}")
        dlines=[f"{k}: {int(v):,}".replace(',','.') for k,v in data.get('por_distrito',{}).items()]
        self.home_district_text.configure(state='normal');self.home_district_text.delete('1.0','end');self.home_district_text.insert('1.0','\n'.join(dlines) if dlines else 'Sin datos');self.home_district_text.configure(state='disabled')
        recent=[(r.get('folio',''),r.get('plano',''),r.get('fecha',''),r.get('categoria',''),r.get('codigo',''),r.get('operacion',''),r.get('distrito','')) for r in data.get('recientes',[])]
        self._replace_tree(self.home_recent_tree,recent)

    def _choose_import(self):
        paths=filedialog.askopenfilenames(title='Cargar datos SENDA', filetypes=[('Archivos SENDA','*.xls *.xlsx *.csv *.json *.txt *.zip *.rar'),('Todos','*.*')])
        if not paths:return
        dialog=tk.Toplevel(self);dialog.title('Importar datos');dialog.transient(self);dialog.grab_set();dialog.resizable(False,False)
        year=tk.StringVar(value=str(date.today().year));quarter=tk.StringVar(value=f'T{((date.today().month-1)//3)+1}');district=tk.StringVar(value='SIN IDENTIFICAR')
        for i,(label,var,vals) in enumerate([('Año',year,None),('Trimestre',quarter,['T1','T2','T3','T4']),('Distrito',district,list(DISTRICTS[1:]))]):
            ttk.Label(dialog,text=label).grid(row=i,column=0,sticky='w',padx=12,pady=8)
            if vals:ttk.Combobox(dialog,textvariable=var,values=vals,state='readonly',width=24).grid(row=i,column=1,padx=12,pady=8)
            else:ttk.Entry(dialog,textvariable=var,width=26).grid(row=i,column=1,padx=12,pady=8)
        ttk.Label(dialog,text=f'{len(paths)} archivo(s) seleccionados · XLS / XLSX / CSV / JSON / TXT / ZIP / RAR').grid(row=3,column=0,columnspan=2,padx=12,pady=4)
        ttk.Label(dialog,text='Los archivos y movimientos repetidos se detectan y no se duplican.',foreground=MUTED).grid(row=4,column=0,columnspan=2,padx=12,pady=(0,4))
        RoundedButton(dialog,text='Importar',command=lambda:self._start_import(dialog,paths,year.get(),quarter.get(),district.get())).grid(row=5,column=0,columnspan=2,pady=12)

    def _start_import(self, dialog, paths, year, quarter, district):
        try:y=int(year)
        except Exception:return messagebox.showerror('SENDA','Año inválido',parent=dialog)
        dialog.destroy();self.status_var.set('Importando archivos... SENDA sigue disponible.');
        def work():
            try:
                result=import_files(self.ctx,paths,year=y,quarter=quarter,district=district)
                self._jobs.put(('import_done',result))
            except Exception as exc:self._jobs.put(('error',f'Importación: {exc}\n\n{traceback.format_exc()}'))
        threading.Thread(target=work,daemon=True).start()

    def _export(self,fmt):
        ext={'json':'.json','csv':'.csv','xlsx':'.xlsx'}[fmt]
        path=filedialog.asksaveasfilename(defaultextension=ext,filetypes=[(fmt.upper(),'*'+ext)])
        if not path:return
        filters=self._filters(self.home_filters)
        def work():
            try:self._jobs.put(('export_done',str(export_movements(self.ctx,fmt,path,filters))))
            except Exception as exc:self._jobs.put(('error',f'Exportación: {exc}\n\n{traceback.format_exc()}'))
        self.status_var.set('Generando exportación...');threading.Thread(target=work,daemon=True).start()

    # -------------------- INFORMACIÓN SENDA --------------------
    def _build_information(self):
        title=ttk.Frame(self.tab_info);title.pack(fill='x')
        ttk.Label(title,text='Información SENDA',style='Title.TLabel').pack(side='left')
        RoundedButton(title,text='+ Expediente manual',command=self._new_case_dialog).pack(side='right')
        self.info_filters=self._filter_bar(self.tab_info, callback=self._reset_info_page)
        actions=ttk.Frame(self.tab_info);actions.pack(fill='x',pady=(0,6))
        ttk.Label(actions,text='Mostrar').pack(side='left')
        self.info_page_size=tk.StringVar(value='25')
        ttk.Combobox(actions,textvariable=self.info_page_size,values=[str(x) for x in PAGE_SIZES],state='readonly',width=5).pack(side='left',padx=5)
        RoundedButton(actions,text='Aplicar',command=self._reset_info_page).pack(side='left')
        RoundedButton(actions,text='Seleccionar visibles',command=self._select_visible_information).pack(side='left',padx=(12,4))
        RoundedButton(actions,text='Limpiar selección',command=self._clear_information_selection).pack(side='left',padx=4)
        self.info_selection_var=tk.StringVar(value='0 seleccionados')
        ttk.Label(actions,textvariable=self.info_selection_var).pack(side='left',padx=10)
        RoundedButton(actions,text='PASAR A CONTROL',command=self._send_to_control,fill=BLUE,fg=WHITE,hover_fill=BLUE_DARK,outline=BLUE).pack(side='right')
        cols=[('sel',34),('folio',120),('plano',130),('distrito',150),('estado',110),('mov',70),('der',60),('alarma',80),('primero',90),('ultimo',90)]
        self.info_tree=self._tree(self.tab_info,cols,headings=('','Folio/Finca','Plano','Distrito','Estado','Mov.','Der.','Alarma','Primero','Último'))
        self.info_tree.bind('<Double-1>',self._info_double_click)
        self.info_tree.bind('<space>',self._toggle_information_selection)
        nav=ttk.Frame(self.tab_info);nav.pack(fill='x',pady=6)
        self.info_page_label=tk.StringVar(value='Página 1')
        RoundedButton(nav,text='‹ Anterior',command=lambda:self._move_info_page(-1)).pack(side='left')
        ttk.Label(nav,textvariable=self.info_page_label).pack(side='left',padx=12)
        RoundedButton(nav,text='Siguiente ›',command=lambda:self._move_info_page(1)).pack(side='left')
        RoundedButton(nav,text='Ver movimientos del folio',command=self._open_selected_entity).pack(side='right')

    def _reset_info_page(self):self._info_offset=0;self.refresh_information()
    def _move_info_page(self,d):
        size=int(self.info_page_size.get());self._info_offset=max(0,self._info_offset+d*size);self.refresh_information()

    def refresh_information(self):
        self._refresh_years(self.info_filters);size=int(self.info_page_size.get())
        data=self.ctx.repo.list_information(self._filters(self.info_filters),limit=size,offset=self._info_offset)
        self._info_rows={}
        rows=[]; tags=[]
        for r in data['rows']:
            key=r['entity_key'];self._info_rows[key]=r
            values, tag = information_alarm_row(r, checked=(key in self._selected_information))
            rows.append(values); tags.append(tag)
        self.info_tree.tag_configure('alarm_red', background=alarm_visual('red')['background'], foreground=alarm_visual('red')['foreground'])
        self.info_tree.tag_configure('alarm_yellow', background=alarm_visual('yellow')['background'], foreground=alarm_visual('yellow')['foreground'])
        self.info_tree.tag_configure('alarm_green', background=alarm_visual('green')['background'], foreground=alarm_visual('green')['foreground'])
        self._replace_tree(self.info_tree,rows,ids=list(self._info_rows.keys()),tags=tags)
        total=data['total'];page=(self._info_offset//size)+1;pages=max(1,(total+size-1)//size)
        if self._info_offset>=total and total:self._info_offset=max(0,(pages-1)*size);return self.refresh_information()
        self.info_page_label.set(f'Página {page} de {pages} · {total} expedientes/folios')
        self.info_selection_var.set(f'{len(self._selected_information)} seleccionados')

    def _toggle_information_selection(self,event=None):
        item=self.info_tree.focus()
        if not item:return
        if item in self._selected_information:self._selected_information.remove(item)
        else:self._selected_information.add(item)
        self.refresh_information()
        return 'break'
    def _info_double_click(self,event):
        region=self.info_tree.identify_region(event.x,event.y);col=self.info_tree.identify_column(event.x)
        if region=='cell' and col=='#1':return self._toggle_information_selection()
        self._open_selected_entity()
    def _select_visible_information(self):
        self._selected_information.update(self.info_tree.get_children());self.refresh_information()
    def _clear_information_selection(self):self._selected_information.clear();self.refresh_information()
    def _send_to_control(self):
        items=[]
        for key in list(self._selected_information):
            r=self._info_rows.get(key)
            if r:items.append({'folio':r['folio'],'plano':r['plano']})
        if not items:return messagebox.showinfo('SENDA','Seleccione al menos un expediente/folio.')
        n=self.ctx.repo.select_cases_for_control(items);self._selected_information.clear();self.refresh_all();self.notebook.select(self.tab_control);messagebox.showinfo('SENDA',f'{n} trámite(s) enviados a Control.')

    def _open_selected_entity(self):
        item=self.info_tree.focus();r=self._info_rows.get(item)
        if not r:return
        self._show_movements_dialog(r['folio'],r['plano'],f"Folio {r['folio'] or '—'} · Plano {r['plano'] or '—'}")

    def _new_case_dialog(self):
        self._case_editor(None)

    # -------------------- CONTROL --------------------
    def _build_control(self):
        ttk.Label(self.tab_control,text='Control',style='Title.TLabel').pack(anchor='w')
        body=ttk.Panedwindow(self.tab_control,orient='horizontal');body.pack(fill='both',expand=True,pady=6)
        left=ttk.Frame(body);right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=3)
        searchbar=ttk.Frame(left);searchbar.pack(fill='x',pady=(0,6));self.control_search=tk.StringVar();ttk.Entry(searchbar,textvariable=self.control_search).pack(side='left',fill='x',expand=True);RoundedButton(searchbar,text='Buscar',command=self.refresh_control).pack(side='left',padx=4)
        self.control_tree=self._tree(left,[('folio',115),('plano',120),('responsable',100),('prioridad',70)],headings=('Folio','Plano','Responsable','Prioridad'))
        self.control_tree.bind('<<TreeviewSelect>>',lambda e:self._load_control_case())
        top=ttk.Frame(right);top.pack(fill='x');self.control_title=tk.StringVar(value='Seleccione un trámite');ttk.Label(top,textvariable=self.control_title,font=('Segoe UI',16,'bold')).pack(side='left')
        self.finalize_btn=RoundedButton(top,text='FINALIZAR',command=self._finalize_active_case,state='disabled',fill=BLUE,fg=WHITE,hover_fill=BLUE_DARK,outline=BLUE);self.finalize_btn.pack(side='right')
        RoundedButton(top,text='Editar expediente',command=lambda:self._case_editor(self._active_control_id)).pack(side='right',padx=5)
        self.control_summary=tk.Text(right,height=7,bg=WHITE,relief='solid',borderwidth=1,font=('Segoe UI',BODY_FONT_SIZE));self.control_summary.pack(fill='x',pady=6)
        catbar=ttk.Frame(right);catbar.pack(fill='x');self.control_category=tk.StringVar(value='TODOS')
        ttk.Label(catbar,text='MOVIMIENTOS').pack(side='left',padx=(0,6))
        for cat in MOVEMENT_CATEGORIES:
            ttk.Radiobutton(catbar,text=cat,variable=self.control_category,value=cat,command=self._refresh_control_movements).pack(side='left',padx=2)
        self.control_mov_tree=self._tree(right,[('fecha',90),('derecho',100),('categoria',110),('operacion',310),('plano',120)],headings=('Fecha','Derecho','Movimiento','Operación','Plano'))
        self.control_page_var=tk.StringVar(value='25');nav=ttk.Frame(right);nav.pack(fill='x',pady=4);ttk.Label(nav,text='Mostrar').pack(side='left');ttk.Combobox(nav,textvariable=self.control_page_var,values=['25','50','100'],state='readonly',width=5).pack(side='left',padx=4);RoundedButton(nav,text='Aplicar',command=self._reset_control_mov_page).pack(side='left')
        self.control_mov_label=tk.StringVar();ttk.Label(nav,textvariable=self.control_mov_label).pack(side='right')

    def refresh_control(self):
        rows=self.ctx.repo.list_control(self.control_search.get())
        self._control_rows={str(r['id']):r for r in rows}
        self._replace_tree(self.control_tree,[(r['folio'],r['plano'],r['responsable'],r['prioridad']) for r in rows],ids=list(self._control_rows.keys()))
        if self._active_control_id and str(self._active_control_id) not in self._control_rows:
            self._active_control_id=None;self.finalize_btn.configure(state='disabled')
    def _load_control_case(self):
        item=self.control_tree.focus();r=self._control_rows.get(item)
        if not r:return
        self._active_control_id=int(item);self._movement_offset=0;self.control_category.set('TODOS');self.finalize_btn.configure(state='normal');self.control_title.set(f"Folio {r['folio'] or '—'} · Plano {r['plano'] or '—'}")
        self._render_control_summary(r);self._refresh_control_movements()
    def _render_control_summary(self,r):
        text=f"Distrito: {r['distrito']}\nResponsable: {r['responsable'] or '—'}    Prioridad: {r['prioridad']}\nEstado: {r['status']}\nObservaciones: {r['note'] or '—'}"
        self.control_summary.configure(state='normal');self.control_summary.delete('1.0','end');self.control_summary.insert('1.0',text);self.control_summary.configure(state='disabled')
    def _reset_control_mov_page(self):self._movement_offset=0;self._refresh_control_movements()
    def _refresh_control_movements(self):
        if not self._active_control_id:return
        size=int(self.control_page_var.get());data=self.ctx.repo.case_movements(self._active_control_id,self.control_category.get(),size,self._movement_offset)
        rows=[(r['fecha'],r['derecho'] or 'GENERAL',r['categoria'],r['operacion'],r['plano']) for r in data['rows']]
        self._replace_tree(self.control_mov_tree,rows)
        rights=', '.join(f"{r['derecho']} ({r['movimientos']})" for r in data.get('rights',[]))
        self.control_mov_label.set(f"{data['total']} movimientos · Derechos: {rights or '—'}")
    def _finalize_active_case(self):
        if not self._active_control_id:return
        r=self.ctx.repo.get_case(self._active_control_id)
        if not messagebox.askyesno('Finalizar trámite',f"Finalizar el trámite del folio {r['folio'] or '—'} y pasarlo a Gestión?\n\nLos movimientos originales no se borran."):return
        self.ctx.repo.finalize_case(self._active_control_id);self._active_control_id=None;self.finalize_btn.configure(state='disabled');self.control_title.set('Seleccione un trámite');self.control_summary.configure(state='normal');self.control_summary.delete('1.0','end');self._replace_tree(self.control_mov_tree,[]);self.refresh_all();self.notebook.select(self.tab_management)

    # -------------------- GESTIÓN --------------------
    def _build_management(self):
        top=ttk.Frame(self.tab_management);top.pack(fill='x')
        ttk.Label(top,text='Gestión',style='Title.TLabel').pack(side='left')
        self.management_search=tk.StringVar();ttk.Entry(top,textvariable=self.management_search,width=25).pack(side='right')
        RoundedButton(top,text='Buscar',command=self.refresh_management).pack(side='right',padx=4)
        RoundedButton(top,text='EXPORTAR BASE JSON',command=lambda:self._export_sync_database('json')).pack(side='right',padx=4)
        RoundedButton(top,text='EXPORTAR BASE EXCEL',command=lambda:self._export_sync_database('xlsx'),fill=BLUE,fg=WHITE,hover_fill=BLUE_DARK,outline=BLUE).pack(side='right',padx=4)

        stats=self._panel(self.tab_management,'Trámites realizados por mes');stats.pack(fill='x',pady=(8,7))
        statbody=tk.Frame(stats,bg=WHITE);statbody.pack(fill='x',padx=10,pady=(2,9))
        self.management_total_var=tk.StringVar(value='0 trámites realizados')
        tk.Label(statbody,textvariable=self.management_total_var,bg=WHITE,fg=NAVY,font=('Segoe UI',PANEL_TITLE_SIZE,'bold')).pack(side='left',padx=(0,16))
        self.management_chart=MonthlyLineChart(statbody,height=155,width=720);self.management_chart.pack(side='left',fill='x',expand=True)
        self.management_district_var=tk.StringVar(value='')
        tk.Label(statbody,textvariable=self.management_district_var,bg=WHITE,fg=MUTED,justify='left',anchor='w',font=('Segoe UI',SMALL_FONT_SIZE)).pack(side='right',padx=(16,0))

        self.management_tree=self._tree(self.tab_management,[('folio',125),('plano',130),('distrito',160),('responsable',120),('finalizado',150),('nota',300)],headings=('Folio','Plano','Distrito','Responsable','Finalizado Control','Observaciones'))
        actions=ttk.Frame(self.tab_management);actions.pack(fill='x',pady=6);RoundedButton(actions,text='Ver movimientos',command=self._management_view).pack(side='left');RoundedButton(actions,text='Editar expediente',command=self._management_edit).pack(side='left',padx=4);RoundedButton(actions,text='Regresar a Información SENDA',command=self._management_return).pack(side='right')
    def refresh_management(self):
        rows=self.ctx.repo.list_management(self.management_search.get());self._management_rows={str(r['id']):r for r in rows}
        self._replace_tree(self.management_tree,[(r['folio'],r['plano'],r['distrito'],r['responsable'],r['finalized_at'] or '',r['note'] or '') for r in rows],ids=list(self._management_rows.keys()))
        stats=self.ctx.repo.management_statistics();self.management_chart.set_data(stats.get('por_mes',{}));self.management_total_var.set(f"{stats.get('total',0):,} trámites realizados".replace(',','.'))
        dlines=[f"{k}: {v:,}".replace(',','.') for k,v in list(stats.get('por_distrito',{}).items())[:5]];self.management_district_var.set('\n'.join(dlines))
    def _export_sync_database(self,fmt):
        ext='.xlsx' if fmt=='xlsx' else '.json';label='Excel' if fmt=='xlsx' else 'JSON'
        path=filedialog.asksaveasfilename(title=f'Exportar Base SENDA · {label}',defaultextension=ext,filetypes=[(label,'*'+ext)])
        if not path:return
        def work():
            try:self._jobs.put(('export_done',str(export_sync_database(self.ctx,fmt,path))))
            except Exception as exc:self._jobs.put(('error',f'Exportación de Base SENDA: {exc}\n\n{traceback.format_exc()}'))
        self.status_var.set('Generando Base SENDA fusionable...');threading.Thread(target=work,daemon=True).start()
    def _management_current(self):return self._management_rows.get(self.management_tree.focus())
    def _management_view(self):
        r=self._management_current();
        if r:self._show_movements_dialog(r['folio'],r['plano'],f"Gestión · {r['folio'] or r['plano']}")
    def _management_edit(self):
        r=self._management_current();
        if r:self._case_editor(r['id'])
    def _management_return(self):
        r=self._management_current();
        if not r:return
        if messagebox.askyesno('SENDA','Regresar este trámite a Información SENDA? El historial quedará auditado.'):
            self.ctx.repo.return_case_to_information(r['id'],'Regresado desde Gestión');self.refresh_all();self.notebook.select(self.tab_info)

    # -------------------- shared dialogs --------------------
    def _case_editor(self,case_id):
        old=self.ctx.repo.get_case(case_id) if case_id else {'folio':'','plano':'','distrito':'SIN IDENTIFICAR','responsable':'','prioridad':'NORMAL','note':''}
        d=tk.Toplevel(self);d.title('Editar expediente' if case_id else 'Nuevo expediente');d.transient(self);d.grab_set();d.geometry('520x390')
        fields={}
        specs=[('Folio / Finca','folio',None),('Plano','plano',None),('Distrito','distrito',list(DISTRICTS[1:])),('Responsable','responsable',None),('Prioridad','prioridad',['BAJA','NORMAL','ALTA','URGENTE'])]
        for i,(label,key,vals) in enumerate(specs):
            ttk.Label(d,text=label).grid(row=i,column=0,sticky='w',padx=12,pady=7);v=tk.StringVar(value=_safe_text(old.get(key)));fields[key]=v
            w=ttk.Combobox(d,textvariable=v,values=vals,state='readonly',width=37) if vals else ttk.Entry(d,textvariable=v,width=40)
            w.grid(row=i,column=1,sticky='ew',padx=12,pady=7)
        ttk.Label(d,text='Observaciones').grid(row=5,column=0,sticky='nw',padx=12,pady=7);note=tk.Text(d,height=6,width=40);note.grid(row=5,column=1,padx=12,pady=7);note.insert('1.0',old.get('note') or '')
        def save():
            payload={k:v.get() for k,v in fields.items()};payload['note']=note.get('1.0','end').strip()
            try:
                if case_id:self.ctx.repo.update_case(case_id,payload)
                else:self.ctx.repo.create_case(payload['folio'],payload['distrito'],payload['note'],plano=payload['plano'],responsable=payload['responsable'],prioridad=payload['prioridad'])
            except Exception as exc:return messagebox.showerror('SENDA',str(exc),parent=d)
            d.destroy();self.refresh_all()
        RoundedButton(d,text='Guardar expediente',command=save).grid(row=6,column=0,columnspan=2,pady=14)

    def _show_movements_dialog(self,folio,plano,title):
        d=tk.Toplevel(self);d.title(title);d.geometry('1160x650');d.transient(self)
        category=tk.StringVar(value='TODOS');page_size=tk.StringVar(value='25');offset={'v':0}
        bar=ttk.Frame(d);bar.pack(fill='x',padx=10,pady=8)
        for cat in MOVEMENT_CATEGORIES:ttk.Radiobutton(bar,text=cat,variable=category,value=cat).pack(side='left',padx=2)
        tree=self._tree(d,[('fecha',90),('derecho',120),('categoria',120),('codigo',80),('operacion',340),('plano',140)],headings=('Fecha','Derecho','Movimiento','Código','Operación','Plano'))
        label=tk.StringVar();nav=ttk.Frame(d);nav.pack(fill='x',padx=10,pady=6);ttk.Label(nav,text='Mostrar').pack(side='left');ttk.Combobox(nav,textvariable=page_size,values=['25','50','100'],state='readonly',width=5).pack(side='left',padx=4);ttk.Label(nav,textvariable=label).pack(side='right')
        def refresh():
            data=self.ctx.repo.entity_movements(folio,plano,category.get(),int(page_size.get()),offset['v']);self._replace_tree(tree,[(r['fecha'],r['derecho'] or 'GENERAL',r['categoria'],r['codigo'],r['operacion'],r['plano']) for r in data['rows']]);label.set(f"{data['total']} movimientos · más antiguo → más reciente")
        def move(delta):offset['v']=max(0,offset['v']+delta*int(page_size.get()));refresh()
        RoundedButton(nav,text='‹ Anterior',command=lambda:move(-1)).pack(side='left',padx=4);RoundedButton(nav,text='Siguiente ›',command=lambda:move(1)).pack(side='left');RoundedButton(nav,text='Aplicar',command=lambda:(offset.update(v=0),refresh())).pack(side='left',padx=4)
        for w in bar.winfo_children():
            try:w.configure(command=lambda:(offset.update(v=0),refresh()))
            except Exception:pass
        refresh()

    # -------------------- widgets / lifecycle --------------------
    def _tree(self,parent,columns,headings):
        wrap=ttk.Frame(parent);wrap.pack(fill='both',expand=True)
        names=[c[0] for c in columns];tree=ttk.Treeview(wrap,columns=names,show='headings',selectmode='browse')
        for (name,width),heading in zip(columns,headings):tree.heading(name,text=heading);tree.column(name,width=width,anchor='w',stretch=name in ('operacion','nota'))
        vs=ttk.Scrollbar(wrap,orient='vertical',command=tree.yview);hs=ttk.Scrollbar(wrap,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        tree.grid(row=0,column=0,sticky='nsew');vs.grid(row=0,column=1,sticky='ns');hs.grid(row=1,column=0,sticky='ew');wrap.rowconfigure(0,weight=1);wrap.columnconfigure(0,weight=1)
        return tree
    def _replace_tree(self,tree,rows,ids=None,tags=None):
        tree.delete(*tree.get_children())
        for i,row in enumerate(rows):
            tree.insert('', 'end', iid=(ids[i] if ids else None), values=row, tags=((tags[i],) if tags else ()))
    def refresh_current_tab(self):
        tab=self.notebook.select()
        if tab==str(self.tab_home):self.refresh_home()
        elif tab==str(self.tab_info):self.refresh_information()
        elif tab==str(self.tab_control):self.refresh_control()
        elif tab==str(self.tab_management):self.refresh_management()
    def refresh_all(self):
        self.refresh_home();self.refresh_information();self.refresh_control();self.refresh_management()
    def _drain_jobs(self):
        try:
            while True:
                kind,payload=self._jobs.get_nowait()
                if kind=='import_done':
                    duplicates=int(payload.get('duplicates',0)); repeated=bool(payload.get('duplicate_import'))
                    self.status_var.set(f"Importación terminada: {payload['inserted']} nuevos, {duplicates} duplicados, {payload['skipped']} omitidos, {payload['errors']} errores")
                    self.refresh_all()
                    if repeated:
                        messagebox.showinfo('SENDA','Archivo/corte ya cargado. No se duplicó ningún movimiento.')
                    else:
                        messagebox.showinfo('SENDA',f"Importación completada.\n\nNuevos: {payload['inserted']}\nDuplicados evitados: {duplicates}\nOmitidos por reglas: {payload['skipped']}\nErrores: {payload['errors']}")
                elif kind=='export_done':self.status_var.set(f'Exportación creada: {payload}');messagebox.showinfo('SENDA','Exportación creada correctamente.')
                elif kind=='error':self.status_var.set('Ocurrió un error. SENDA sigue abierta.');messagebox.showerror('SENDA',payload)
        except queue.Empty:pass
        self.after(150,self._drain_jobs)
    def _on_close(self):self.destroy()


def main(argv=None):
    parser=argparse.ArgumentParser(description='SENDA.V0 Desktop')
    parser.add_argument('--data-dir')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    ctx=create_context(args.data_dir)
    if args.check:
        print(f'SENDA.V0 Desktop OK | DB={ctx.repo.path}')
        return 0
    app=SendaDesktop(args.data_dir);app.mainloop();return 0

if __name__=='__main__':
    raise SystemExit(main())
