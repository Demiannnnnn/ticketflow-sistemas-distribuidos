#!/bin/bash
set -e

echo "Running Patroni post_init hook to create database..."

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -p 5432 -U postgres; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "PostgreSQL is ready. Creating database 'ticketflow' if it does not exist..."

# Create the database if it doesn't exist
# We use -v ON_ERROR_STOP=1 to make psql exit with an error code if creation fails
psql -h localhost -p 5432 -U postgres -v ON_ERROR_STOP=1 <<EOF
CREATE DATABASE ticketflow;
EOF

echo "Database 'ticketflow' creation script finished."
