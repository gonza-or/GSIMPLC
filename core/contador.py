class Contador:
    def __init__(self, identificador, preseleccion):
        self.identificador = int(identificador)
        self.preseleccion = int(preseleccion)
        self.acumulado = 0
        self.completado = False
        self.contando_arriba = False
        self.contando_abajo = False

    def cambiar_preseleccion(self, preseleccion):
        self.preseleccion = int(preseleccion)

    def incrementar(self):
        self.acumulado = self.acumulado + 1

    def decrementar(self):
        if self.acumulado > 0:
            self.acumulado = self.acumulado - 1

    def evaluar_completado(self):
        self.completado = self.acumulado >= self.preseleccion

    def actualizar(self, acumulado, completado, contando_arriba,
                   contando_abajo):
        self.acumulado = int(acumulado)
        self.completado = bool(completado)
        self.contando_arriba = bool(contando_arriba)
        self.contando_abajo = bool(contando_abajo)

    def copia(self):
        copia = Contador(self.identificador, self.preseleccion)
        copia.acumulado = self.acumulado
        copia.completado = self.completado
        copia.contando_arriba = self.contando_arriba
        copia.contando_abajo = self.contando_abajo
        return copia

    def a_diccionario(self):
        return {
            "PRE": self.preseleccion,
            "ACC": self.acumulado,
            "DN": self.completado,
            "CU": self.contando_arriba,
            "CD": self.contando_abajo,
        }
