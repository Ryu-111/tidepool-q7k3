package dev.ryu.jevprobe;

import org.json.*;
import java.util.*;

/** Runs on Android's real org.json implementation; no provider requests. */
final class JsonSelfTest {
    static String run() {
        try {
            Policy.Field field = new Policy.Field(0, Policy.Shape.TEXT,
                Arrays.asList(Policy.label("email"), Policy.label("SENTINEL_PRIVATE_VALUE")));
            Policy.Field password = new Policy.Field(1, Policy.Shape.PASSWORD, Collections.emptyList());
            List<Policy.Field> fields = Arrays.asList(field, password);
            JSONObject payload = Jev.payload(fields);
            String serialized = payload.toString();
            if (serialized.contains("SENTINEL") || serialized.contains("PASSWORD")
                || serialized.contains("value") || serialized.contains("url")) throw new AssertionError();
            Policy.Field incompatible = new Policy.Field(2, Policy.Shape.EMAIL,
                Arrays.asList(Policy.Kind.STREET));
            if (Jev.payload(Arrays.asList(incompatible, password))
                .getJSONObject("questions").length() != 0) throw new AssertionError();
            JSONObject answer = new JSONObject().put("type", "choice").put("choice", "EMAIL")
                .put("confidence", .99).put("probabilities", new JSONObject().put("EMAIL", .99).put("UNKNOWN", .01));
            JSONObject answers = new JSONObject().put("f0", answer);
            JSONObject body = new JSONObject().put("answers", answers);
            if (Jev.parse(body.toString(), fields).get(0) != Policy.Kind.EMAIL) throw new AssertionError();
            answer.put("confidence", .5);
            if (!Jev.parse(body.toString(), fields).isEmpty()) throw new AssertionError();
            answer.put("confidence", .99);
            answer.put("choice", "PASSWORD"); reject(body, fields);
            answer.put("choice", "EMAIL");
            answers.put("f999", answer); reject(body, fields); answers.remove("f999");
            answer.put("confidence", "0.99"); reject(body, fields); answer.put("confidence", .99);
            answer.getJSONObject("probabilities").put("UNKNOWN", .99); reject(body, fields);
            android.util.Log.i("JevProbeTest", "JSON PASS: privacy, choices, keys, probabilities, failure handling");
            return "PASS（通信なし・漏えい防止／応答検証）";
        } catch (Exception | AssertionError failure) {
            android.util.Log.e("JevProbeTest", "JSON FAIL");
            return "FAIL";
        }
    }
    private static void reject(JSONObject body, List<Policy.Field> fields) throws Exception {
        try { Jev.parse(body.toString(), fields); }
        catch (JSONException expected) { return; }
        throw new AssertionError("Expected rejection");
    }
}
