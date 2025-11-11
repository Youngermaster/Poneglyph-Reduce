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
        
        // Add CORS headers for all responses
        addCorsHeaders(ex);
        
        ex.getResponseHeaders().set("Content-Type", contentType);
        ex.sendResponseHeaders(code, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }
    
    /**
     * Add CORS headers to allow Dashboard access from different origin
     */
    public static void addCorsHeaders(HttpExchange ex) {
        ex.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        ex.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        ex.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type, Authorization");
        ex.getResponseHeaders().set("Access-Control-Max-Age", "3600");
    }
    
    /**
     * Handle CORS preflight requests
     */
    public static boolean handleCorsPreflightRequest(HttpExchange ex) throws IOException {
        if ("OPTIONS".equals(ex.getRequestMethod())) {
            addCorsHeaders(ex);
            ex.sendResponseHeaders(200, 0);
            return true; // Request handled
        }
        return false; // Request not handled, continue processing
    }

    public static void respondJson(HttpExchange ex, int code, Object obj) throws IOException {
        respond(ex, code, gson.toJson(obj), "application/json");
    }
}
