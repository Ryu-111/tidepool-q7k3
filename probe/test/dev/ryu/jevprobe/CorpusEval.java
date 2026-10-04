package dev.ryu.jevprobe;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Classifies corpus fields (TSV from corpus/eval/to_tsv.py on stdin) with the local rules only,
 * the same way ProbeService builds evidence. Prints one line per field: page, index, kind, evidence.
 */
public final class CorpusEval {
    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        Map<String, List<String[]>> pages = new LinkedHashMap<>();
        for (String line; (line = in.readLine()) != null; ) {
            String[] cols = line.split("\t", 4);
            pages.computeIfAbsent(cols[0], k -> new ArrayList<>()).add(cols);
        }
        for (Map.Entry<String, List<String[]>> page : pages.entrySet()) {
            if (page.getValue().size() > 32) {  // the product rejects such forms as TOO_MANY_FIELDS
                for (String[] cols : page.getValue())
                    System.out.println(page.getKey() + "\t" + cols[1] + "\tTOO_MANY\t" + cols[2] + "\t"
                        + (cols.length > 3 ? cols[3].replace('\u001f', '|') : ""));
                continue;
            }
            List<Policy.Field> fields = new ArrayList<>();
            Map<Integer, Policy.Kind> chosen = new LinkedHashMap<>();
            for (String[] cols : page.getValue()) {
                int id = Integer.parseInt(cols[1]);
                Set<Policy.Kind> hints = EnumSet.noneOf(Policy.Kind.class);
                if (cols.length > 3) {
                    for (String pair : cols[3].split("\u001f")) {
                        int eq = pair.indexOf('=');
                        String key = pair.substring(0, eq), text = pair.substring(eq + 1);
                        if (key.equals("maxlength")) continue;
                        if (key.equals("autocomplete")) {
                            for (String token : text.split("\\s+")) hints.add(Policy.label(token));
                        } else {
                            hints.add(Policy.label(text));
                        }
                    }
                }
                hints.remove(Policy.Kind.UNKNOWN);
                Policy.Field field = new Policy.Field(id, Policy.Shape.valueOf(cols[2]), hints);
                fields.add(field);
                chosen.put(id, field.localChoice());
            }
            Map<Integer, Policy.Kind> refined = Policy.refine(fields, chosen);
            for (String[] cols : page.getValue()) {
                int id = Integer.parseInt(cols[1]);
                System.out.println(page.getKey() + "\t" + id + "\t" + refined.get(id) + "\t"
                    + cols[2] + "\t" + (cols.length > 3 ? cols[3].replace('\u001f', '|') : ""));
            }
        }
    }
}
