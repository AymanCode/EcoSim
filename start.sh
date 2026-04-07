#!/usr/bin/env sh
set -eu

docker compose up --build -d

printf '\nEcoSim is starting.\n'
printf 'Dashboard: http://localhost:5173\n'
printf 'Health:    http://localhost:5173/health\n\n'
printf 'To stop the stack:\n'
printf 'docker compose down\n'
