class Temporizador:
    def __init__(self, identificador, preseleccion):
        self.identificador = int(identificador)
        self.preseleccion = int(preseleccion)
        self.acumulado = 0
        self.habilitado = False
        self.completado = False
        self.temporizando = False

    def cambiar_preseleccion(self, preseleccion):
        self.preseleccion = int(preseleccion)

    def actualizar(self, habilitado, acumulado, completado, temporizando):
        self.habilitado = bool(habilitado)
        self.acumulado = int(acumulado)
        self.completado = bool(completado)
        self.temporizando = bool(temporizando)

    def copia(self):
        copia = Temporizador(self.identificador, self.preseleccion)
        copia.acumulado = self.acumulado
        copia.habilitado = self.habilitado
        copia.completado = self.completado
        copia.temporizando = self.temporizando
        return copia

    def a_diccionario(self):
        return {
            "PRE": self.preseleccion,
            "ACC": self.acumulado,
            "EN": self.habilitado,
            "DN": self.completado,
            "TT": self.temporizando,
        }
