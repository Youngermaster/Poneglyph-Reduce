# syntax=docker/dockerfile:1

FROM eclipse-temurin:17-jdk AS build
WORKDIR /app

# copia wrapper y build files primero (layer cache)
COPY gradlew gradle/ build.gradle settings.gradle ./
# copia código
COPY src ./src

# build distribución (bin + libs)
RUN ./gradlew --no-daemon clean installDist

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/build/install/road-poneglyph /app
EXPOSE 8080
# script generado por 'installDist' según settings.gradle
CMD ["./bin/road-poneglyph"]
