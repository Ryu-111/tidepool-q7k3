package dev.ryu.jevprobe;

import org.json.*;
import java.io.*;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.net.ssl.HttpsURLConnection;

/** No values, URLs, raw labels, page text, cookies or histories can enter this transport. */
final class Jev {
    static JSONObject payload(List<Policy.Field> fields) throws JSONException {
        return payload(fields, fields);
    }
    /**
     * The table describes every non-password field of the form (type, hint kinds and the kind
     * already resolved on-device) so the model can use the neighbors; questions cover only
     * {@code ask}. Both contain fixed vocabulary only.
     */
    static JSONObject payload(List<Policy.Field> context, List<Policy.Field> ask) throws JSONException {
        JSONArray table = new JSONArray();
        for (Policy.Field field : context) {
            if (field.shape == Policy.Shape.PASSWORD) continue;
            JSONArray hints = new JSONArray();
            for (Policy.Kind hint : field.hints) hints.put(hint.name());
            JSONObject row = new JSONObject().put("id", field.id).put("type", field.shape.name())
                .put("hints", hints);
            if (field.localChoice() != Policy.Kind.UNKNOWN) row.put("resolved", field.localChoice().name());
            table.put(row);
        }
        JSONObject questions = new JSONObject();
        for (Policy.Field field : ask) {
            if (field.shape == Policy.Shape.PASSWORD || field.choices().size() < 2) continue;
            JSONObject criteria = new JSONObject();
            // Fixed vocabulary descriptions only; no page text reaches the model.
            for (Policy.Kind kind : field.choices()) criteria.put(kind.name(), Policy.describe(kind));
            questions.put("f" + field.id, new JSONObject().put("type", "choice")
                .put("instructions", "Choose the semantic kind for field " + field.id
                    + " of a Japanese profile form, using the sanitized field table in document"
                    + " order. Hints come from the page's own labels; when hints nest (one kind is"
                    + " part of another), prefer the most specific kind that fits the neighboring"
                    + " fields. Choose UNKNOWN only if the hints genuinely conflict.")
                .put("criteria", criteria));
        }
        return new JSONObject().put("model", "jev-latest")
            .put("state", new JSONObject().put("fields", table)).put("questions", questions);
    }
    static Map<Integer, Policy.Kind> parse(String body, List<Policy.Field> fields)
        throws JSONException {
        if (body.length() > 65536) throw new JSONException("size");
        JSONObject answers = new JSONObject(body).getJSONObject("answers");
        JSONObject questions = payload(fields).getJSONObject("questions");
        if (!keys(answers).equals(keys(questions))) throw new JSONException("answer keys");
        Map<Integer, Policy.Kind> result = new HashMap<>();
        for (Policy.Field field : fields) {
            if (!questions.has("f" + field.id)) continue;
            JSONObject answer = answers.getJSONObject("f" + field.id);
            if (!"choice".equals(answer.getString("type"))) throw new JSONException("type");
            Policy.Kind chosen;
            try { chosen = Policy.Kind.valueOf(answer.getString("choice")); }
            catch (IllegalArgumentException invalid) { throw new JSONException("choice"); }
            Object rawConfidence = answer.get("confidence");
            if (!(rawConfidence instanceof Number)) throw new JSONException("confidence");
            double confidence = ((Number) rawConfidence).doubleValue();
            if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1)
                throw new JSONException("confidence");
            JSONObject probabilities = answer.getJSONObject("probabilities");
            Set<String> expected = new HashSet<>();
            for (Policy.Kind kind : field.choices()) expected.add(kind.name());
            if (!keys(probabilities).equals(expected) || !expected.contains(chosen.name()))
                throw new JSONException("options");
            double total = 0;
            double largest = 0;
            for (String key : expected) {
                Object raw = probabilities.get(key);
                if (!(raw instanceof Number)) throw new JSONException("probability");
                double p = ((Number) raw).doubleValue();
                if (!Double.isFinite(p) || p < 0 || p > 1) throw new JSONException("probability");
                total += p;
                largest = Math.max(largest, p);
            }
            if (Math.abs(total - 1) > 0.001
                || probabilities.getDouble(chosen.name()) < largest) throw new JSONException("distribution");
            if (Policy.accepted(field, chosen, confidence)) result.put(field.id, chosen);
        }
        return result;
    }
    private static Set<String> keys(JSONObject object) {
        Set<String> result = new HashSet<>();
        Iterator<String> keys = object.keys();
        while (keys.hasNext()) result.add(keys.next());
        return result;
    }
    static Map<Integer, Policy.Kind> request(List<Policy.Field> context, List<Policy.Field> fields,
                                             String apiKey)
        throws Exception {
        if (apiKey == null || apiKey.isEmpty() || apiKey.contains("\n") || apiKey.contains("\r"))
            throw new IOException("API key required");
        JSONObject payload = payload(context, fields);
        if (payload.getJSONObject("questions").length() == 0)
            throw new IOException("No compatible fields to classify");
        HttpsURLConnection connection = (HttpsURLConnection)
            new URL("https://openrouter.ai/api/v1/systemone").openConnection();
        try {
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(8000);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + apiKey);
            connection.setDoOutput(true);
            byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream out = connection.getOutputStream()) { out.write(bytes); }
            if (connection.getResponseCode() != 200) throw new IOException("Provider request failed");
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            try (InputStream in = connection.getInputStream()) {
                byte[] block = new byte[4096];
                int count;
                while ((count = in.read(block)) != -1) {
                    if (buffer.size() + count > 65536) throw new IOException("Response too large");
                    buffer.write(block, 0, count);
                }
            }
            return parse(new String(buffer.toByteArray(), StandardCharsets.UTF_8), fields);
        } finally { connection.disconnect(); }
    }
    private Jev() {}
}
