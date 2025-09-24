#!/bin/bash
set -e

SERVICE_NAME="doge-bot-dev"

case "$1" in
  up)
    docker compose up -d $SERVICE_NAME
    ;;
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f $SERVICE_NAME
    ;;
  rebuild)
    docker compose build --no-cache $SERVICE_NAME
    ;;
  exec)
    shift
    docker exec -it $SERVICE_NAME "$@"
    ;;
  *)
    echo "Usage: $0 {up|down|logs|rebuild|exec}"
    exit 1
    ;;
esac
