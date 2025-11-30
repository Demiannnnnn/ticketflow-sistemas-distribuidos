### 3. Estrategia de Tolerancia a Fallos y Pruebas

Se implementará un modelo de **Consistencia Eventual**. Las pruebas a documentar serán:

**1) Prueba de Integridad (Caída de App 2):** Se simulará la caída del contenedor de Python (Facturación) durante una compra.

*   **Resultado Esperado:** El usuario recibe confirmación "Compra Exitosa" (procesada por el sistema). El ticket PDF queda "En Proceso". Al levantar la App 2, el sistema consume la cola de RabbitMQ y envía el correo automáticamente.

**2) Prueba de Disponibilidad de Datos (Caída de MariaDB):** Se detendrá la instancia principal de MariaDB.

*   **Resultado Esperado:** El Orquestador detecta el fallo y redirige las consultas de lectura a la réplica. La venta se detiene momentáneamente (o pasa a modo solo lectura), pero el usuario puede seguir consultando sus tickets previos sin error 500.

**3) Prueba de Caída del Middleware:** Se simulará la caída de los contenedores de RabbitMQ y la aplicación Go que funciona como orquestador.

*   **Resultado Esperado:** Durante la interrupción, cualquier intento de nueva compra en el Portal de Venta (App3) fallará, mostrando un error controlado al usuario. Las consultas de tickets existentes seguirán funcionando. Al restaurar los servicios de Middleware, el sistema volverá a la normalidad, permitiendo procesar nuevas compras sin pérdida de datos.
