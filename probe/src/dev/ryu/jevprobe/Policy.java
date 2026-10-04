package dev.ryu.jevprobe;

import java.text.Normalizer;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Value-free policy shared by the fixture probe and its JVM security tests. */
public final class Policy {
    // Component bits. A kind is the set of profile components it renders, so a combined field
    // ("住所") and its parts ("都道府県", "番地") can be compared structurally, never by value.
    // Address, in writing order: 都道府県, 市・郡, 区・町村, 町名, 丁目, 番, 号, 建物.
    static final int R = 1, M = 2, W = 4, T = 8, N1 = 16, N2 = 32, N3 = 64, B = 128;
    private static final int C = M | W, N = N1 | N2 | N3;
    private static final int FN = 1 << 8, GN = 1 << 9;                        // name
    private static final int FK = 1 << 10, GK = 1 << 11;                      // name reading
    private static final int P1 = 1 << 12, P2 = 1 << 13;                      // postal code
    private static final int T1 = 1 << 14, T2 = 1 << 15, T3 = 1 << 16;        // phone
    private static final int BY = 1 << 24, BM = 1 << 25, BD = 1 << 26;        // birth date
    private static final int ERA = 1 << 23;                                   // 元号 (昭和/平成/令和)
    private static final int CO = 1 << 17, DEPT = 1 << 18, TITLE = 1 << 19;  // work
    public enum Kind {
        FAMILY(FN), GIVEN(GN), FULL_NAME(FN | GN),
        FAMILY_KANA(FK), GIVEN_KANA(GK), FULL_KANA(FK | GK),
        POSTAL(P1 | P2), POSTAL_1(P1), POSTAL_2(P2),
        REGION(R), MUNICIPALITY(M), WARD(W), CITY(C), TOWN(T),
        CHOME(N1), BAN(N2), GO(N3), BAN_GO(N2 | N3), BLOCK(N), TOWN_CHOME(T | N1), STREET(T | N),
        BUILDING(B), REGION_CITY(R | C), CITY_TOWN(C | T), CITY_STREET(C | T | N),
        WARD_STREET(W | T | N), ADDRESS_LINES(T | N | B), AFTER_MUNICIPALITY(W | T | N | B),
        ADDRESS_AFTER_REGION(C | T | N | B), ADDRESS_NO_BUILDING(R | C | T | N),
        ADDRESS_FULL(R | C | T | N | B),
        PHONE(T1 | T2 | T3), PHONE_1(T1), PHONE_2(T2), PHONE_3(T3),
        BIRTHDATE(ERA | BY | BM | BD), BIRTH_YEAR(BY), BIRTH_MONTH(BM), BIRTH_DAY(BD),
        BIRTH_ERA(ERA), BIRTH_ERA_YEAR(BY),  // 平成 + 2 when the era is chosen in its own field
        COMPANY(CO), DEPARTMENT(DEPT), JOB_TITLE(TITLE),
        GENDER(1 << 27), AGE(1 << 28), COUNTRY(1 << 29),
        EMAIL(1 << 20), USERNAME(1 << 21), PASSWORD(1 << 22), UNKNOWN(0);
        public final int mask;
        Kind(int mask) { this.mask = mask; }
        public boolean within(Kind other) { return mask != 0 && (mask & ~other.mask) == 0; }
        static Kind of(int mask) {
            for (Kind kind : values()) if (kind.mask == mask && mask != 0) return kind;
            return UNKNOWN;
        }
    }
    /** LIST = select, TOGGLE = one radio/checkbox, DATE = a native date control. */
    public enum Shape { TEXT, PASSWORD, EMAIL, TEL, NUMBER, LIST, TOGGLE, DATE }
    private static final Map<String, Kind> LABELS = new HashMap<>();
    // Decorations that do not change a field's meaning. Anything else keeps the label UNKNOWN.
    private static final Set<String> NOTES = new HashSet<>();
    private static final Pattern BRACKET = Pattern.compile("[(\\[【「]([^)\\]】」]*)[)\\]】」]");
    static {
        labels(Kind.FAMILY, "family-name", "lastname", "last name", "last_name", "sei", "name_sei",
            "name1", "姓", "名字", "苗字", "氏", "姓(漢字)", "name_last");
        labels(Kind.GIVEN, "given-name", "firstname", "first name", "first_name", "mei", "name_mei",
            "name2", "名", "名(漢字)", "name_first");
        labels(Kind.FULL_NAME, "name", "fullname", "full name", "full_name", "氏名", "名前",
            "フルネーム", "氏名(漢字)", "name_full");
        labels(Kind.FAMILY_KANA, "姓(フリガナ)", "セイ", "姓(カナ)", "せい", "姓(ふりがな)",
            "フリガナ(姓)", "ふりがな(姓)", "kana_sei", "sei_kana", "kana1", "family-name-kana");
        labels(Kind.GIVEN_KANA, "名(フリガナ)", "メイ", "名(カナ)", "めい", "名(ふりがな)",
            "フリガナ(名)", "ふりがな(名)", "kana_mei", "mei_kana", "kana2", "given-name-kana");
        labels(Kind.FULL_KANA, "フリガナ", "ふりがな", "カナ", "よみがな", "氏名(フリガナ)",
            "氏名(カナ)", "氏名(ふりがな)", "kana", "furigana", "name_kana");
        labels(Kind.POSTAL, "postal-code", "postal code", "postal_code", "zip", "zipcode", "zip code",
            "postcode", "郵便番号", "〒", "address_home_zip");
        labels(Kind.POSTAL_1, "zip1", "zip01", "zip_1", "postal1", "postcode1", "郵便番号1",
            "郵便番号(前半)", "郵便番号(上3桁)");
        labels(Kind.POSTAL_2, "zip2", "zip02", "zip_2", "postal2", "postcode2", "郵便番号2",
            "郵便番号(後半)", "郵便番号(下4桁)");
        labels(Kind.REGION, "address-level1", "都道府県", "state", "province", "pref",
            "prefecture", "address_home_state");
        labels(Kind.CITY, "address-level2", "市区町村", "市町村", "市区郡", "city", "address_home_city");
        labels(Kind.TOWN, "address-level3", "町名", "町域", "address_home_dependent_locality");
        labels(Kind.BLOCK, "house number", "address_home_house_number");
        labels(Kind.STREET, "address-line1", "番地", "町名番地", "町名・番地", "町域・番地",
            "丁目・番地", "street", "address_home_line1");
        labels(Kind.BUILDING, "address-line2", "建物名", "建物名・部屋番号", "建物名・号室",
            "マンション名", "building", "address2", "addr2", "住所2", "address_home_line2");
        labels(Kind.CITY_STREET, "市区町村・番地", "市区町村番地", "市区町村・町名・番地");
        labels(Kind.ADDRESS_AFTER_REGION, "市区町村以降", "都道府県以降");
        labels(Kind.ADDRESS_NO_BUILDING, "address1", "addr1", "住所1");
        labels(Kind.ADDRESS_LINES, "street-address", "address_home_street_address");
        labels(Kind.ADDRESS_FULL, "住所", "address", "所在地");
        labels(Kind.PHONE, "tel", "tel-national", "phone", "phone number", "telephone", "電話",
            "電話番号", "携帯電話番号", "連絡先電話番号", "phone_home_whole_number",
            "phone_home_city_and_number");
        labels(Kind.PHONE_1, "tel1", "tel01", "tel_1", "phone1", "tel-area-code", "電話番号1",
            "phone_home_city_code");
        labels(Kind.PHONE_2, "tel2", "tel02", "tel_2", "phone2", "tel-local-prefix", "電話番号2");
        labels(Kind.PHONE_3, "tel3", "tel03", "tel_3", "phone3", "tel-local-suffix", "電話番号3");
        labels(Kind.EMAIL, "email", "email address", "e-mail", "mail", "メールアドレス", "メール",
            "email_confirm", "email2", "mail_confirm", "メールアドレス(確認)",
            "メールアドレス(確認用)", "確認用メールアドレス", "email_address");
        labels(Kind.USERNAME, "username", "user name", "ユーザー名");
        labels(Kind.CITY, "市区町村名", "市区郡町村", "市区町村・郡");
        labels(Kind.MUNICIPALITY, "市", "市郡", "市・郡", "郡市", "市名", "city1", "address_city1");
        labels(Kind.WARD, "区", "区町村", "区・町村", "区名", "町村", "city2", "address_city2", "ward");
        labels(Kind.TOWN, "町名・字", "町・字", "大字", "字", "町域名", "town");
        labels(Kind.CHOME, "丁目", "chome");
        labels(Kind.BAN, "番", "ban");
        labels(Kind.GO, "号", "go");
        labels(Kind.BAN_GO, "番・号", "番地・号", "番号");
        labels(Kind.BLOCK, "丁目・番・号", "番地のみ");
        labels(Kind.TOWN_CHOME, "町名・丁目", "町域・丁目", "町名丁目");
        labels(Kind.REGION_CITY, "都道府県・市区町村", "都道府県市区町村", "都道府県・市区郡");
        labels(Kind.BIRTHDATE, "生年月日", "誕生日", "birthday", "birthdate", "birth date", "bday",
            "date of birth", "dob", "birth", "birth_date", "birthday_date");
        labels(Kind.BIRTH_YEAR, "生年", "生まれ年", "誕生年", "birth_year", "birthyear", "birth_y",
            "bday-year", "bday_year", "birthday_year", "birth-year");
        labels(Kind.BIRTH_MONTH, "誕生月", "生まれ月", "birth_month", "birthmonth", "birth_m",
            "bday-month", "bday_month", "birthday_month", "birth-month");
        labels(Kind.BIRTH_DAY, "誕生日(日)", "birth_day", "birthday_day", "birth_d", "bday-day",
            "bday_day", "birth-day");
        labels(Kind.GENDER, "性別", "gender", "sex", "seibetsu", "男性", "女性", "男", "女");
        labels(Kind.AGE, "年齢", "age", "ご年齢");
        labels(Kind.BIRTH_ERA, "元号", "年号", "和暦", "era", "birth_era", "gengo");
        labels(Kind.COMPANY, "会社名", "勤務先", "勤務先名", "法人名", "企業名", "団体名", "組織名",
            "company", "company name", "company_name", "organization", "html_type_organization",
            "company_name_field");
        labels(Kind.DEPARTMENT, "部署", "部署名", "所属", "所属部署", "department", "division", "dept");
        labels(Kind.JOB_TITLE, "役職", "役職名", "職位", "job title", "job_title", "jobtitle");
        labels(Kind.COUNTRY, "国", "国名", "国・地域", "country", "country-name", "国籍",
            "address_home_country", "html_type_country_name", "html_type_country_code");
        // Chrome forwards the page author's autocomplete tokens as HTML_TYPE_*.
        labels(Kind.FULL_NAME, "html_type_name");
        labels(Kind.FAMILY, "html_type_family_name");
        labels(Kind.GIVEN, "html_type_given_name");
        labels(Kind.POSTAL, "html_type_postal_code");
        labels(Kind.REGION, "html_type_address_level1");
        labels(Kind.CITY, "html_type_address_level2");
        labels(Kind.TOWN, "html_type_address_level3");
        labels(Kind.STREET, "html_type_address_line1");
        labels(Kind.BUILDING, "html_type_address_line2");
        labels(Kind.ADDRESS_LINES, "html_type_street_address");
        labels(Kind.PHONE, "html_type_tel", "html_type_tel_national");
        labels(Kind.PHONE_1, "html_type_tel_area_code");
        labels(Kind.PHONE_2, "html_type_tel_local_prefix");
        labels(Kind.PHONE_3, "html_type_tel_local_suffix");
        labels(Kind.EMAIL, "html_type_email", "email_address");
        // Password is recognized from the control's password type, never from model output.
        for (String note : new String[]{"必須", "任意", "半角", "全角", "半角数字", "全角数字",
            "半角英数", "半角英数字", "全角カナ", "全角カタカナ", "半角カナ", "半角カタカナ",
            "ひらがな", "カタカナ", "ハイフンなし", "ハイフン無し", "ハイフン不要", "ハイフンあり",
            "ハイフン有り", "ハイフン必須", "数字のみ", "required", "optional", "確認用", "西暦",
            "和暦", "数字", "スラッシュなし", "スラッシュ区切り", "yyyy/mm/dd", "yyyymmdd", "漢字",
            "カレンダー", "カレンダー入力", "カレンダーから選択", "選択"})
            NOTES.add(normalize(note));
    }
    private static String normalize(String value) {
        return Normalizer.normalize(value, Normalizer.Form.NFKC).trim().toLowerCase(Locale.ROOT);
    }
    private static void labels(Kind kind, String... labels) {
        for (String label : labels) LABELS.put(normalize(label), kind);
    }
    public static Kind label(String raw) {
        if (raw == null || raw.length() > 128) return Kind.UNKNOWN;
        String text = normalize(raw);
        Kind exact = LABELS.get(text);
        if (exact != null) return exact;
        // Drop only known annotations: "(必須)", "【半角数字】", "※...", "例)...", "*", leading ご/お.
        text = text.replaceAll("[※*].*$", "").replaceAll("\\s*例[:)].*$", "");
        StringBuilder kept = new StringBuilder();
        Matcher m = BRACKET.matcher(text);
        int last = 0;
        while (m.find()) {
            String note = m.group(1).trim();
            boolean known = note.startsWith("例");
            for (String part : note.split("[・、,\\s]+"))
                known |= NOTES.contains(part)
                    || part.matches("(半角|全角)?(数字|英数字)?[0-9]{1,2}(桁|文字)(以内)?");
            if (!known) continue;  // meaningful brackets such as 姓(フリガナ) stay in the label
            kept.append(text, last, m.start());
            last = m.end();
        }
        kept.append(text.substring(last));
        text = kept.toString().trim();
        Kind result = LABELS.get(text);
        if (result == null && (text.startsWith("ご") || text.startsWith("お")))
            result = LABELS.get(text.substring(1));
        return result == null ? Kind.UNKNOWN : result;
    }
    /** Fixed, value-free description of a kind for the model's choice criteria. */
    public static String describe(Kind kind) {
        switch (kind) {
            case FAMILY: return "family name only";
            case GIVEN: return "given name only";
            case FULL_NAME: return "full name (family and given) in one field";
            case FAMILY_KANA: return "reading of the family name only (kana)";
            case GIVEN_KANA: return "reading of the given name only (kana)";
            case FULL_KANA: return "reading of the full name in one field (kana)";
            case POSTAL: return "whole Japanese postal code in one field";
            case POSTAL_1: return "first 3 digits of a postal code split into two fields";
            case POSTAL_2: return "last 4 digits of a postal code split into two fields";
            case REGION: return "prefecture only";
            case MUNICIPALITY: return "city or county part only (市・郡), when the ward is separate";
            case WARD: return "ward, town or village part only (区・町村), when the city is separate";
            case CITY: return "city/ward/town/village only";
            case TOWN: return "town area name only";
            case CHOME: return "chome number only";
            case BAN: return "ban number only";
            case GO: return "go number only";
            case BAN_GO: return "ban and go numbers";
            case BLOCK: return "block/house number only";
            case TOWN_CHOME: return "town area name and chome";
            case STREET: return "town area and block number, after the city";
            case BUILDING: return "building name and room number only";
            case REGION_CITY: return "prefecture and city in one field";
            case CITY_TOWN: return "city and town area";
            case CITY_STREET: return "city, town area and block number, without prefecture or building";
            case WARD_STREET: return "ward, town area and block number, after a separate city field";
            case AFTER_MUNICIPALITY: return "address after a separate city field, including building";
            case BIRTHDATE: return "whole date of birth in one field";
            case BIRTH_YEAR: return "year of birth";
            case BIRTH_MONTH: return "month of birth";
            case BIRTH_DAY: return "day of month of birth";
            case BIRTH_ERA: return "Japanese era name of the birth year (e.g. Showa, Heisei)";
            case BIRTH_ERA_YEAR: return "year of birth counted within a separately chosen Japanese era";
            case COMPANY: return "company or organization name";
            case DEPARTMENT: return "department or division";
            case JOB_TITLE: return "job title or position";
            case GENDER: return "gender";
            case AGE: return "age in years";
            case COUNTRY: return "country";
            case ADDRESS_LINES: return "street lines after the city, including building";
            case ADDRESS_AFTER_REGION: return "full address after the prefecture, including building";
            case ADDRESS_NO_BUILDING: return "address from prefecture to block number, without building";
            case ADDRESS_FULL: return "entire address in one field";
            case PHONE: return "whole phone number in one field";
            case PHONE_1: return "first part (area code) of a phone number split into three fields";
            case PHONE_2: return "middle part of a phone number split into three fields";
            case PHONE_3: return "last part of a phone number split into three fields";
            case EMAIL: return "email address, including a confirmation field";
            case USERNAME: return "login username";
            case PASSWORD: return "password";
            default: return "none of the above or ambiguous";
        }
    }
    public static final class Field {
        public final int id;
        public final Shape shape;
        public final Set<Kind> hints;
        public Field(int id, Shape shape, Collection<Kind> hints) {
            if (id < 0 || id >= 32 || shape == null) throw new IllegalArgumentException("field");
            this.id = id;
            this.shape = shape;
            EnumSet<Kind> safe = EnumSet.noneOf(Kind.class);
            safe.addAll(hints);
            safe.remove(Kind.UNKNOWN);
            safe.remove(Kind.PASSWORD);
            this.hints = Collections.unmodifiableSet(safe);
        }
        public Kind localChoice() {
            if (shape == Shape.PASSWORD) return Kind.PASSWORD;
            // Hints agree when every hint contains the most specific one,
            // e.g. autocomplete=postal-code with name=zip1 means POSTAL_1.
            Kind best = null;
            for (Kind hint : hints) {
                if (!compatible(hint)) continue;
                if (best == null || hint.within(best)) best = hint;
            }
            if (best == null) return Kind.UNKNOWN;
            for (Kind hint : hints) if (compatible(hint) && !best.within(hint)) return Kind.UNKNOWN;
            return best;
        }
        public boolean compatible(Kind kind) {
            if (kind == Kind.UNKNOWN) return true;
            if (shape == Shape.PASSWORD) return kind == Kind.PASSWORD;
            if (kind == Kind.PASSWORD) return false;
            if (shape == Shape.EMAIL) return kind == Kind.EMAIL;
            boolean digits = kind.within(Kind.PHONE) || kind.within(Kind.POSTAL)
                || kind.within(Kind.BIRTHDATE) && kind != Kind.BIRTH_ERA || kind == Kind.AGE;
            if (shape == Shape.TEL) return kind.within(Kind.PHONE) || kind.within(Kind.POSTAL);
            if (shape == Shape.NUMBER) return digits || kind == Kind.CHOME || kind == Kind.BAN || kind == Kind.GO;
            // BIRTHDATE is admitted only so three 生年月日 selects can be split by refine(); an
            // unsplit date has no matching option and is never written into a select.
            if (shape == Shape.LIST) return EnumSet.of(Kind.REGION, Kind.CITY, Kind.MUNICIPALITY,
                Kind.WARD, Kind.BIRTHDATE, Kind.BIRTH_YEAR, Kind.BIRTH_MONTH, Kind.BIRTH_DAY,
                Kind.BIRTH_ERA, Kind.BIRTH_ERA_YEAR, Kind.JOB_TITLE,
                Kind.GENDER, Kind.AGE, Kind.COUNTRY).contains(kind);
            if (shape == Shape.TOGGLE) return kind == Kind.GENDER;
            if (shape == Shape.DATE) return kind == Kind.BIRTHDATE;
            return true;
        }
        public List<Kind> choices() {
            List<Kind> options = new ArrayList<>();
            // A model cannot invent a semantic field unsupported by sanitized local evidence.
            for (Kind hint : hints) if (compatible(hint)) options.add(hint);
            options.add(Kind.UNKNOWN);
            return options;
        }
    }
    /**
     * Resolves form structure after classification, from kinds and document order only.
     * 1. A run of adjacent identical kinds with as many fields as components is a split field
     *    (郵便番号 3+4, 電話 3 parts, 姓/名 under one label), assigned in component order.
     * 2. A combined field drops components that another field on the form fills by itself
     *    (住所 next to 都道府県 becomes ADDRESS_AFTER_REGION).
     */
    public static Map<Integer, Kind> refine(List<Field> fields, Map<Integer, Kind> chosen) {
        Kind[] kinds = new Kind[fields.size()];
        for (int i = 0; i < kinds.length; i++)
            kinds[i] = chosen.getOrDefault(fields.get(i).id, Kind.UNKNOWN);
        for (int start = 0; start < kinds.length; ) {
            int end = start + 1;
            while (end < kinds.length && kinds[end] == kinds[start]) end++;
            if (kinds[start] == Kind.BIRTHDATE && end - start == 3) {
                // 生年月日 as [年][月][日] under one label; four boxes include the 元号 (generic rule).
                Kind[] parts = {Kind.BIRTH_YEAR, Kind.BIRTH_MONTH, Kind.BIRTH_DAY};
                System.arraycopy(parts, 0, kinds, start, 3);
            } else if (kinds[start] != Kind.UNKNOWN && end - start > 1
                && end - start == Integer.bitCount(kinds[start].mask)) {
                int remaining = kinds[start].mask;
                for (int i = start; i < end; i++) {
                    int lowest = Integer.lowestOneBit(remaining);
                    remaining &= ~lowest;
                    kinds[i] = Kind.of(lowest);
                }
            }
            start = end;
        }
        // With a separate 元号 field, the year field takes the year within that era.
        if (Arrays.asList(kinds).contains(Kind.BIRTH_ERA))
            for (int i = 0; i < kinds.length; i++) if (kinds[i] == Kind.BIRTH_YEAR) kinds[i] = Kind.BIRTH_ERA_YEAR;
        Map<Integer, Kind> result = new HashMap<>();
        for (int i = 0; i < kinds.length; i++) {
            int mask = kinds[i].mask;
            for (int j = 0; j < kinds.length; j++) {
                if (j != i && kinds[j].within(kinds[i]) && kinds[j] != kinds[i]) mask &= ~kinds[j].mask;
            }
            Kind refined = mask == kinds[i].mask ? kinds[i] : Kind.of(mask);
            result.put(fields.get(i).id, fields.get(i).compatible(refined) ? refined : Kind.UNKNOWN);
        }
        return result;
    }
    public static boolean allowedTarget(String packageName, String scheme, String domain) {
        // Probe only. No user credentials, arbitrary websites or production HTTPS exceptions.
        return "com.android.chrome".equals(packageName) && "http".equals(scheme)
            && "localhost".equals(domain);
    }
    public static boolean accepted(Field field, Kind chosen, double confidence) {
        return field.shape != Shape.PASSWORD && chosen != Kind.PASSWORD
            && field.choices().contains(chosen) && Double.isFinite(confidence)
            && confidence >= 0.90 && confidence <= 1.0;
    }
    private Policy() {}
}
