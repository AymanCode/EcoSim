#!/usr/bin/env sh
set -eu

docker compose up --build -d --wait

printf '\nEcoSim is ready.\n'
printf 'Dashboard: http://localhost:5173\n'
printf 'Health:    http://localhost:5173/health\n\n'
printf 'To stop the stack:\n'
printf 'docker compose down\n'
