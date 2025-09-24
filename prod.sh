#!/bin/bash
set -e

SERVICE=doge-bot-prod

case "$1" in
  up)
    docker compose up -d $SERVICE
    ;;
  down)
    docker compose down $SERVICE
    ;;
  logs)
    docker compose logs -f $SERVICE
    ;;
  rebuild)
    docker compose build --no-cache $SERVICE
    ;;
  *)
    echo "Usage: $0 {up|down|logs|rebuild}"
    exit 1
    ;;
esac
