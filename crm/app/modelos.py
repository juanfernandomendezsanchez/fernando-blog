"""Tablas de la base de datos del CRM.

Cada tabla hereda de ModeloBase, que ya trae id, creado_en y modificado_en.
Las fechas se guardan siempre en UTC (ver app/configuracion.py para mostrarlas
en hora de Caracas).

Los campos que en el papel son "una lista cerrada de opciones" (por ejemplo el
canal de una interaccion, o el estado de una tarea) se guardan como texto simple
en vez de un tipo especial: son pocas palabras, se validan donde se usan, y asi
el codigo se mantiene facil de leer.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def hora_actual_utc() -> datetime:
    return datetime.utcnow()


class ModeloBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    creado_en: datetime = Field(default_factory=hora_actual_utc)
    modificado_en: datetime = Field(default_factory=hora_actual_utc)


def dividir_etiquetas(texto: Optional[str]) -> list[str]:
    """Convierte el texto guardado ("marca,ecommerce") en una lista de etiquetas."""
    if not texto:
        return []
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def unir_etiquetas(etiquetas: list[str]) -> str:
    """Convierte una lista de etiquetas en el texto que se guarda en la base de datos."""
    return ",".join(etiqueta.strip() for etiqueta in etiquetas if etiqueta.strip())


class Empresa(ModeloBase, table=True):
    nombre: str
    sector: Optional[str] = None
    tamano: Optional[str] = None
    ciudad: Optional[str] = None
    sitio_o_red: Optional[str] = None
    # Valores esperados: baja, media, alta.
    madurez_de_marca: Optional[str] = None


class Contacto(ModeloBase, table=True):
    nombre: str
    correo: Optional[str] = Field(default=None, index=True)
    telefono: Optional[str] = Field(default=None, index=True)
    usuario_instagram: Optional[str] = None
    # Valores esperados: correo, whatsapp, instagram.
    canal_preferido: Optional[str] = None
    # Valores esperados: referido, instagram, whatsapp, correo, web, evento, otro.
    origen: str = "otro"
    referido_por_id: Optional[int] = Field(default=None, foreign_key="contacto.id")
    empresa_id: Optional[int] = Field(default=None, foreign_key="empresa.id")
    etiquetas: Optional[str] = None
    puntuacion: int = 0
    no_contactar: bool = False
    notas: Optional[str] = None


class Servicio(ModeloBase, table=True):
    nombre: str
    # Valores esperados: asesoria, consultoria, venta.
    linea: str
    precio_base: float = 0.0
    moneda: str = "USD"
    duracion: Optional[str] = None
    entregables: Optional[str] = None
    plantilla_propuesta: Optional[str] = None


class Oportunidad(ModeloBase, table=True):
    contacto_id: int = Field(foreign_key="contacto.id")
    servicio_id: int = Field(foreign_key="servicio.id")
    # Etapas validas: ver reglas/embudo.yaml (campo "etapas").
    etapa: str = "Nuevo"
    valor_estimado: Optional[float] = None
    moneda: str = "USD"
    probabilidad: int = 5
    fecha_cierre_esperada: Optional[datetime] = None
    # Se copia del contacto al crear la oportunidad.
    origen: str = "otro"
    siguiente_paso: Optional[str] = None
    fecha_siguiente_paso: Optional[datetime] = None
    en_riesgo: bool = False
    # Valores esperados (solo si etapa es Perdido): ver reglas/embudo.yaml.
    motivo_perdida: Optional[str] = None
    ultima_actividad_en: datetime = Field(default_factory=hora_actual_utc)


class Interaccion(ModeloBase, table=True):
    oportunidad_id: int = Field(foreign_key="oportunidad.id")
    fecha: datetime = Field(default_factory=hora_actual_utc)
    # Valores esperados: correo, whatsapp, instagram, llamada, reunion.
    canal: str
    # Valores esperados: entrante, saliente.
    direccion: str
    resumen: Optional[str] = None
    hilo_id_externo: Optional[str] = Field(default=None, index=True)
    requiere_respuesta: bool = False


class Tarea(ModeloBase, table=True):
    oportunidad_id: Optional[int] = Field(default=None, foreign_key="oportunidad.id")
    tipo: Optional[str] = None
    descripcion: str
    fecha_limite: Optional[datetime] = None
    # Valores esperados: baja, media, alta.
    prioridad: str = "media"
    # Valores esperados: pendiente, hecha, cancelada.
    estado: str = "pendiente"
    # Valores esperados: yo, regla, sincronizacion.
    creada_por: str = "yo"


class Propuesta(ModeloBase, table=True):
    oportunidad_id: int = Field(foreign_key="oportunidad.id")
    version: int = 1
    monto: float = 0.0
    moneda: str = "USD"
    alcance: Optional[str] = None
    fecha_envio: Optional[datetime] = None
    vigencia_hasta: Optional[datetime] = None
    # Valores esperados: borrador, enviada, vista, aceptada, rechazada.
    estado: str = "borrador"
    documento_adjunto_url: Optional[str] = None


class Proyecto(ModeloBase, table=True):
    oportunidad_id: int = Field(foreign_key="oportunidad.id")
    inicio: Optional[datetime] = None
    entrega: Optional[datetime] = None
    estado: str = "en_curso"
    satisfaccion: Optional[int] = None
    acepta_testimonio: bool = False


class Hito(ModeloBase, table=True):
    proyecto_id: int = Field(foreign_key="proyecto.id")
    nombre: str
    monto: float = 0.0
    moneda: str = "USD"
    fecha_esperada: Optional[datetime] = None
    # Valores esperados: pendiente, activo, cumplido.
    estado: str = "pendiente"


class Pago(ModeloBase, table=True):
    proyecto_id: int = Field(foreign_key="proyecto.id")
    hito_id: Optional[int] = Field(default=None, foreign_key="hito.id")
    monto: float = 0.0
    moneda: str = "USD"
    metodo: Optional[str] = None
    fecha: Optional[datetime] = None
    # Valores esperados: pendiente, recibido, vencido.
    estado: str = "pendiente"


class Borrador(ModeloBase, table=True):
    oportunidad_id: Optional[int] = Field(default=None, foreign_key="oportunidad.id")
    canal: str
    asunto: Optional[str] = None
    cuerpo: str
    regla_origen: Optional[str] = None
    # Valores esperados: pendiente, aprobado, descartado, enviado.
    estado: str = "pendiente"


class Evento(ModeloBase, table=True):
    # Formato modulo.hecho, por ejemplo "correo.nuevo" u "oportunidad.cambio_etapa".
    tipo: str
    clave_unica: str = Field(unique=True, index=True)
    datos: Optional[str] = None
    # Valores esperados: yo, regla, sincronizacion.
    origen: str = "sincronizacion"
    procesado: bool = False


class Bitacora(ModeloBase, table=True):
    entidad: str
    entidad_id: int
    campo: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    # Valores esperados: yo, regla, sincronizacion.
    origen: str = "yo"
    fecha: datetime = Field(default_factory=hora_actual_utc)
