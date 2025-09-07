package http;

import com.google.gson.Gson;
import com.sun.net.httpserver.HttpExchange;

import java.io.*;
import java.nio.charset.StandardCharsets;

public final class HttpUtils {
    private static final Gson gson = new Gson();

    private HttpUtils() {
    }

    public static String readBody(HttpExchange ex) throws IOException {
        try (InputStream is = ex.getRequestBody()) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    public static void respond(HttpExchange ex, int code, String body, String contentType) throws IOException {
        byte[] bytes = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", contentType);
        ex.sendResponseHeaders(code, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }

    public static void respondJson(HttpExchange ex, int code, Object obj) throws IOException {
        respond(ex, code, gson.toJson(obj), "application/json");
    }
}
