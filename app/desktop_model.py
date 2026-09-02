from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import ensure_data_dirs
from .repository import Repository
from .importers.engine import ImportEngine
from .services.exports import export_csv, export_json, export_xlsx

MOVEMENT_CATEGORIES = (
    'TODOS','FINCAS','HIPOTECAS','GRAVÁMENES','SEGREGACIONES',
    'ANOTACIONES','HISTÓRICOS','CERRADAS','OTROS'
)
PAGE_SIZES = (25, 50, 100)
DISTRICTS = ('TODOS','PUERTO VIEJO','LA VIRGEN','HORQUETAS','LLANURAS DEL GASPAR','CUREÑA','SIN IDENTIFICAR')
ALARMS = ('TODAS','red','yellow','green')
QUARTERS = ('TODOS','T1','T2','T3','T4')
MONTHS = ('TODOS',) + tuple(str(i) for i in range(1,13))

@dataclass
class DesktopContext:
    data_root: Path
    dirs: dict
    repo: Repository
    importer: ImportEngine


def create_context(data_root: str | Path | None = None) -> DesktopContext:
    root, dirs = ensure_data_dirs(Path(data_root) if data_root else None)
    repo = Repository(dirs['database'] / 'senda_v0.sqlite')
    return DesktopContext(root, dirs, repo, ImportEngine(repo))


def filters_from_values(*, year='TODOS', quarter='TODOS', month='TODOS', district='TODOS', alarm='TODAS', movement='TODOS', search='') -> dict:
    out = {'search': str(search or '').strip()}
    if year not in (None,'','TODOS','ALL'): out['year'] = int(year)
    if quarter not in (None,'','TODOS','ALL'): out['quarter'] = quarter
    if month not in (None,'','TODOS','ALL'): out['month'] = int(month)
    if district not in (None,'','TODOS','ALL'): out['district'] = district
    if alarm not in (None,'','TODAS','ALL'): out['alarm'] = alarm
    if movement not in (None,'','TODOS','ALL'): out['movement_type'] = movement
    return out


def available_years(repo: Repository) -> list[str]:
    with repo.connection() as c:
        years = [str(r['anio']) for r in c.execute('SELECT DISTINCT anio FROM movements WHERE anio IS NOT NULL ORDER BY anio DESC')]
    return ['TODOS', *years]


def import_files(ctx: DesktopContext, paths: Iterable[str | Path], *, year: int, quarter: str, district: str):
    return ctx.importer.import_paths(paths, year=year, quarter=quarter, district=district)


def export_movements(ctx: DesktopContext, fmt: str, target: str | Path, filters: dict | None = None):
    target = Path(target)
    fmt = fmt.lower()
    if fmt == 'json': return export_json(ctx.repo, filters or {}, target)
    if fmt == 'csv': return export_csv(ctx.repo, filters or {}, target)
    if fmt in ('xlsx','excel'): return export_xlsx(ctx.repo, filters or {}, target)
    raise ValueError('Formato de exportación no soportado')
