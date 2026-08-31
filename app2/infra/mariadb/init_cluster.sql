-- Usuarios de Sistema para Arquitectura HA

-- 1. Usuario para Replicación (Slave -> Master)
CREATE USER IF NOT EXISTS 'repl_user'@'%' IDENTIFIED BY 'repl_password';
GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'%';

-- 2. Usuario para Orchestrator (Topology Manager)
-- Necesita permisos amplios para ver estados y reconfigurar replicación
CREATE USER IF NOT EXISTS 'orch_user'@'%' IDENTIFIED BY 'orch_password';
GRANT SUPER, PROCESS, REPLICATION SLAVE, REPLICATION CLIENT, RELOAD ON *.* TO 'orch_user'@'%';
-- GRANT SELECT ON mysql.slave_master_info TO 'orch_user'@'%'; -- Eliminado por incompatibilidad con MariaDB default

-- 3. Usuario para ProxySQL Monitor
CREATE USER IF NOT EXISTS 'monitor_user'@'%' IDENTIFIED BY 'monitor_password';
GRANT USAGE ON *.* TO 'monitor_user'@'%';

FLUSH PRIVILEGES;
