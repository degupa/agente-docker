# agente-docker
Es un agente de data engineer para trabajar y probar la IA
COMANDO A USAR UNA VEZ LEVANTADO :
docker build -t agente-data-engineer . 
agente-docker  : docker run --rm --network red-datos -v "${PWD}:/app" --add-host=host.docker.internal:host-gateway agente-data-engineer
