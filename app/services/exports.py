from __future__ import annotations
import csv, json, sys
from pathlib import Path

COLS=['folio','derecho','plano','fecha','codigo','operacion','tipo','fuente','cedula','titular','anio','mes','trimestre','distrito','archivo_origen','alarma']

def iter_pages(repo,filters,page_size=5000):
    offset=0
    while True:
        rows=repo.list_movements(filters,limit=page_size,offset=offset)
        if not rows:break
        yield rows
        offset += len(rows)
        if len(rows)<page_size:break

def export_json(repo,filters,target:Path):
    with target.open('w',encoding='utf-8') as f:
        f.write('{"sistema":"SENDA.V0","movimientos":['); first=True
        for page in iter_pages(repo,filters):
            for row in page:
                if not first:f.write(',')
                json.dump({k:row.get(k,'') for k in COLS},f,ensure_ascii=False); first=False
        f.write(']}')
    return target

def export_csv(repo,filters,target:Path):
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLS,delimiter=';');w.writeheader()
        for page in iter_pages(repo,filters):
            for row in page:w.writerow({k:row.get(k,'') for k in COLS})
    return target

def export_xlsx(repo,filters,target:Path):
    vendor=Path(__file__).resolve().parents[2]/'vendor'
    if str(vendor) not in sys.path:sys.path.insert(0,str(vendor))
    import xlsxwriter
    wb=xlsxwriter.Workbook(str(target),{'constant_memory':True})
    ws=wb.add_worksheet('Movimientos'); hdr=wb.add_format({'bold':True,'bg_color':'#DCE6F1','border':1}); datefmt=wb.add_format({'num_format':'yyyy-mm-dd'})
    for c,name in enumerate(COLS):ws.write(0,c,name.upper(),hdr)
    rix=1
    for page in iter_pages(repo,filters):
        for row in page:
            for c,name in enumerate(COLS):ws.write(rix,c,row.get(name,''))
            rix+=1
    ws.freeze_panes(1,0); ws.autofilter(0,0,max(0,rix-1),len(COLS)-1)
    ws.set_column(0,len(COLS)-1,16);ws.set_column(5,5,36);ws.set_column(9,9,30)
    wb.close();return target
