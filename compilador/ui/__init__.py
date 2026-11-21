"""Componentes de la interfaz grafica del IDE."""

from .archivos import ManejadorArchivos
from .busqueda import BusquedaReemplazo
from .ide import IDECompilador
from .numeros_linea import NumerosLinea
from .sidebar import Sidebar

__all__ = [
    "BusquedaReemplazo",
    "IDECompilador",
    "ManejadorArchivos",
    "NumerosLinea",
    "Sidebar",
]
