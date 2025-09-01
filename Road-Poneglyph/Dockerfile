# syntax=docker/dockerfile:1

# Usamos gradle preinstalado
FROM gradle:8.7.0-jdk17 AS build
WORKDIR /home/gradle/project

# Copiamos primero los archivos de build (cache friendly)
COPY build.gradle settings.gradle ./
# Luego el código
COPY src ./src

# Construcción distribución (bin + libs)
RUN gradle --no-daemon clean installDist

FROM eclipse-temurin:17-jre
WORKDIR /app
# Gracias a settings.gradle, el nombre de la dist es "road-poneglyph"
COPY --from=build /home/gradle/project/build/install/road-poneglyph /app
EXPOSE 8080
# script generado por 'installDist' según settings.gradle
CMD ["./bin/road-poneglyph"]
