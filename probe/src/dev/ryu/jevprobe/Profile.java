package dev.ryu.jevprobe;

import java.text.Normalizer;
import java.time.LocalDate;
import java.time.Period;
import java.time.ZoneOffset;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Synthetic profile and on-device formatting. Page text used here (labels, placeholders,
 * option captions, maxlength) only shapes the rendered dummy value and never leaves the device.
 */
public final class Profile {
    /** How a field wants its value written. null means "no evidence, use the default". */
    public static final class Format {
        public final Boolean hyphen, fullWidth, datePad;
        public final boolean hiragana, dateKanji, era, blockKanji;
        public final String nameSeparator, dateSeparator;
        public final int maxLength;
        Format(Boolean hyphen, Boolean fullWidth, boolean hiragana, String nameSeparator,
               String dateSeparator, Boolean datePad, boolean dateKanji, boolean era,
               boolean blockKanji, int maxLength) {
            this.hyphen = hyphen; this.fullWidth = fullWidth; this.hiragana = hiragana;
            this.nameSeparator = nameSeparator; this.dateSeparator = dateSeparator;
            this.datePad = datePad; this.dateKanji = dateKanji; this.era = era;
            this.blockKanji = blockKanji; this.maxLength = maxLength;
        }
        public static final Format DEFAULT =
            new Format(null, null, false, null, null, null, false, false, false, -1);
        private static final Pattern DIGITS_HYPHEN =
            Pattern.compile("[0-9]{2,5}-[0-9]{2,4}(-[0-9]{3,4})?");
        private static final Pattern DIGITS = Pattern.compile("[0-9]{7,11}");
        private static final Pattern HIRAGANA = Pattern.compile("[\\u3041-\\u309F\\u30FC\\s\\u3000]+");
        private static final Pattern NAME = Pattern.compile("[^\\s\\u3000]+([\\s\\u3000])[^\\s\\u3000]+");
        private static final Pattern DATE_SEP =
            Pattern.compile("(?i)([0-9]{4}|yyyy)([/.-])([0-9]{1,2}|mm?)\\2([0-9]{1,2}|dd?)");
        private static final Pattern DATE_COMPACT = Pattern.compile("(?i)[0-9]{8}|yyyymmdd");
        private static final Pattern DATE_KANJI =
            Pattern.compile("(?i).*([0-9]+|y+)年([0-9]+|m+)月([0-9]+|d+)日.*");
        private static final Pattern PADDED_PART = Pattern.compile("(?i)0[0-9]|mm|dd");
        public static Format parse(Collection<String> texts, int maxLength) {
            Boolean hyphen = null, fullWidth = null, datePad = null;
            boolean hiragana = false, dateKanji = false, era = false, blockKanji = false;
            String separator = null, dateSeparator = null;
            for (String raw : texts) {
                if (raw == null || raw.length() > 128) continue;
                String text = raw.trim();
                String folded = Normalizer.normalize(text, Normalizer.Form.NFKC);
                if (folded.matches(".*ハイフン(なし|無し|不要|を除く|を入れない).*")) hyphen = false;
                else if (folded.matches(".*ハイフン(あり|有り|必須|を含|を入れ).*")) hyphen = true;
                if (folded.contains("半角")) fullWidth = false;
                else if (folded.contains("全角")) fullWidth = true;
                if (folded.contains("ふりがな") || folded.contains("ひらがな")) hiragana = true;
                if (folded.matches(".*(和暦|昭和|平成|令和).*")) era = true;
                if (folded.contains("丁目") && folded.contains("番")) blockKanji = true;
                // Placeholder examples: "例）100-0001", "03-1234-5678", "山田　太郎", "1990/01/01".
                String example = text.replaceFirst("^(例|例え?ば)?[:：)）]?\\s*", "").trim();
                String exampleFolded = Normalizer.normalize(example, Normalizer.Form.NFKC)
                    .replace('ー', '-').replace('−', '-');
                Matcher date = DATE_SEP.matcher(exampleFolded);
                if (date.matches()) {
                    dateSeparator = date.group(2);
                    datePad = date.group(3).length() == 2;
                    continue;
                }
                if (DATE_COMPACT.matcher(exampleFolded).matches()) {
                    dateSeparator = "";
                    datePad = true;
                }
                Matcher kanji = DATE_KANJI.matcher(exampleFolded);
                if (kanji.matches()) {
                    dateKanji = true;
                    datePad = kanji.group(2).length() == 2;
                    continue;
                }
                if (PADDED_PART.matcher(exampleFolded).matches()) datePad = true;
                if (DIGITS_HYPHEN.matcher(exampleFolded).matches()) {
                    if (hyphen == null) hyphen = true;
                    if (fullWidth == null && !example.equals(exampleFolded)) fullWidth = true;
                } else if (DIGITS.matcher(exampleFolded).matches()) {
                    if (hyphen == null) hyphen = false;
                    if (fullWidth == null && !example.equals(exampleFolded)) fullWidth = true;
                } else if (!example.isEmpty() && example.length() <= 16) {
                    Matcher name = NAME.matcher(example);
                    if (name.matches() && separator == null) separator = name.group(1);
                    if (HIRAGANA.matcher(example).matches() && example.length() > 1) hiragana = true;
                }
            }
            return new Format(hyphen, fullWidth, hiragana, separator, dateSeparator, datePad,
                dateKanji, era, blockKanji, maxLength > 0 ? maxLength : -1);
        }
    }
    // Dummy components only. The product replaces this with unlocked vault values.
    static final String FAMILY = "試験", GIVEN = "太郎", FAMILY_KANA = "シケン", GIVEN_KANA = "タロウ";
    static final String[] POSTAL = {"100", "0001"};
    static final String REGION = "神奈川県", MUNICIPALITY = "横浜市", WARD = "中区", TOWN = "検証町",
        BUILDING = "ダミービル101";
    static final String[] BLOCK = {"1", "2", "3"};  // 丁目, 番, 号
    static final String[] PHONE = {"090", "0000", "0000"};
    static final LocalDate BIRTH = LocalDate.of(1990, 4, 5);
    static final String GENDER = "女性", COUNTRY = "日本";
    static final String COMPANY = "ダミー株式会社", DEPARTMENT = "検証部", JOB_TITLE = "主任";
    static final String EMAIL = "dummy@example.invalid", USERNAME = "jev-demo-user",
        PASSWORD = "DUMMY_ONLY_not_a_credential";
    private static final Set<String> GENDER_WORDS = words("女性", "女", "female", "f", "woman", "women");
    private static final Set<String> COUNTRY_WORDS = words("日本", "日本国", "japan", "jp", "jpn");

    public static String render(Policy.Kind kind, Format format, Policy.Shape shape) {
        return render(kind, format, shape, LocalDate.now());
    }
    /** Returns the text for this field, or null if it cannot be written within its constraints. */
    public static String render(Policy.Kind kind, Format format, Policy.Shape shape, LocalDate today) {
        if (format == null) format = Format.DEFAULT;
        boolean numeric = shape == Policy.Shape.NUMBER;
        boolean full = !numeric && Boolean.TRUE.equals(format.fullWidth);
        String value;
        switch (kind) {
            case FAMILY: value = FAMILY; break;
            case GIVEN: value = GIVEN; break;
            case FULL_NAME: value = name(FAMILY, GIVEN, format, full); break;
            case FAMILY_KANA: value = kana(FAMILY_KANA, format); break;
            case GIVEN_KANA: value = kana(GIVEN_KANA, format); break;
            case FULL_KANA: value = kana(name(FAMILY_KANA, GIVEN_KANA, format, full), format); break;
            case POSTAL: value = digits(POSTAL, format, numeric); break;
            case POSTAL_1: value = POSTAL[0]; break;
            case POSTAL_2: value = POSTAL[1]; break;
            case PHONE: value = digits(PHONE, format, numeric); break;
            case PHONE_1: value = PHONE[0]; break;
            case PHONE_2: value = PHONE[1]; break;
            case PHONE_3: value = PHONE[2]; break;
            case BIRTHDATE: return birthdate(format, shape, full);
            case BIRTH_YEAR: value = format.era && !numeric ? eraYear(BIRTH) : String.valueOf(BIRTH.getYear()); break;
            case BIRTH_MONTH: value = pad(BIRTH.getMonthValue(), Boolean.TRUE.equals(format.datePad)); break;
            case BIRTH_DAY: value = pad(BIRTH.getDayOfMonth(), Boolean.TRUE.equals(format.datePad)); break;
            case AGE: value = String.valueOf(Period.between(BIRTH, today).getYears()); break;
            case BIRTH_ERA: value = eraName(BIRTH); break;
            case BIRTH_ERA_YEAR: value = eraYear(BIRTH).substring(2); break;
            case COMPANY: value = COMPANY; break;
            case DEPARTMENT: value = DEPARTMENT; break;
            case JOB_TITLE: value = JOB_TITLE; break;
            case GENDER: value = GENDER; break;
            case COUNTRY: value = COUNTRY; break;
            case EMAIL: return fits(EMAIL, format);
            case USERNAME: return fits(USERNAME, format);
            case PASSWORD: return fits(PASSWORD, format);
            case UNKNOWN: return null;
            default: value = address(kind.mask, format.blockKanji, full);
        }
        if (value == null) return null;
        if (full) value = toFullWidth(value);
        String fitted = fits(value, format);
        // A name without explicit separator evidence may drop the space to fit a short field.
        // Other values are never shortened: a truncated address is worse than an empty field.
        if (fitted == null && format.nameSeparator == null
            && (kind == Policy.Kind.FULL_NAME || kind == Policy.Kind.FULL_KANA))
            fitted = fits(value.replaceAll("[ 　]", ""), format);
        return fitted;
    }
    private static String birthdate(Format format, Policy.Shape shape, boolean full) {
        if (shape == Policy.Shape.DATE) return BIRTH.toString();  // HTML date value: 1990-04-05
        boolean kanji = format.dateKanji || format.era;
        // "1990/04/05" by default; "1990年4月5日" unless the example pads ("01月").
        boolean pad = kanji ? Boolean.TRUE.equals(format.datePad) : !Boolean.FALSE.equals(format.datePad);
        String year = format.era ? eraYear(BIRTH) : String.valueOf(BIRTH.getYear());
        String month = pad(BIRTH.getMonthValue(), pad), day = pad(BIRTH.getDayOfMonth(), pad);
        String sep = format.dateSeparator != null ? format.dateSeparator : "/";
        String value = kanji ? year + "年" + month + "月" + day + "日" : year + sep + month + sep + day;
        if (full) value = toFullWidth(value);
        String fitted = fits(value, format);
        if (fitted == null && format.dateSeparator == null && !format.dateKanji && !format.era)
            fitted = fits(year + pad(BIRTH.getMonthValue(), true) + pad(BIRTH.getDayOfMonth(), true), format);
        return fitted;
    }
    static String eraYear(LocalDate date) {
        String[] names = {"令和", "平成", "昭和", "大正", "明治"};
        LocalDate[] starts = {LocalDate.of(2019, 5, 1), LocalDate.of(1989, 1, 8),
            LocalDate.of(1926, 12, 25), LocalDate.of(1912, 7, 30), LocalDate.of(1868, 1, 25)};
        for (int i = 0; i < names.length; i++)
            if (!date.isBefore(starts[i])) return names[i] + (date.getYear() - starts[i].getYear() + 1);
        return String.valueOf(date.getYear());
    }
    static String eraName(LocalDate date) {
        String year = eraYear(date);
        return year.matches("[0-9]+") ? null : year.substring(0, 2);
    }
    private static final Map<String, Set<String>> ERA_WORDS = new HashMap<>();
    static {
        ERA_WORDS.put("令和", words("令和", "r", "reiwa"));
        ERA_WORDS.put("平成", words("平成", "h", "heisei"));
        ERA_WORDS.put("昭和", words("昭和", "s", "showa"));
        ERA_WORDS.put("大正", words("大正", "t", "taisho"));
        ERA_WORDS.put("明治", words("明治", "m", "meiji"));
    }
    private static int westernYear(String era, int year) {
        switch (era) {
            case "令和": return 2018 + year;
            case "平成": return 1988 + year;
            case "昭和": return 1925 + year;
            case "大正": return 1911 + year;
            case "明治": return 1867 + year;
            default: return -1;
        }
    }
    private static String pad(int value, boolean pad) {
        return pad && value < 10 ? "0" + value : String.valueOf(value);
    }
    private static String address(int mask, boolean blockKanji, boolean full) {
        StringBuilder out = new StringBuilder();
        String[] parts = {REGION, MUNICIPALITY, WARD, TOWN};
        int[] bits = {Policy.R, Policy.M, Policy.W, Policy.T};
        for (int i = 0; i < parts.length; i++) if ((mask & bits[i]) != 0) out.append(parts[i]);
        // 丁目・番・号: "1-2-3" by default, "1丁目2番3号" when the page asks for it, and
        // "検証町1丁目" when only the chome follows the town.
        int[] blockBits = {Policy.N1, Policy.N2, Policy.N3};
        String[] suffixes = {"丁目", "番", "号"};
        List<String> block = new ArrayList<>();
        List<String> kanji = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            if ((mask & blockBits[i]) == 0) continue;
            block.add(BLOCK[i]);
            kanji.add(BLOCK[i] + suffixes[i]);
        }
        boolean single = block.size() == 1 && out.length() == 0;  // a lone 丁目/番/号 box
        boolean chomeOnly = block.size() == 1 && (mask & Policy.N1) != 0;
        if (!block.isEmpty()) out.append(single ? block.get(0)
            : blockKanji || chomeOnly ? String.join("", kanji) : String.join("-", block));
        if ((mask & Policy.B) != 0) {
            if (out.length() > 0) out.append(full ? "　" : " ");
            out.append(BUILDING);
        }
        return out.length() == 0 ? null : out.toString();
    }
    private static String name(String family, String given, Format format, boolean full) {
        String separator = format.nameSeparator != null ? format.nameSeparator : full ? "　" : " ";
        return family + separator + given;
    }
    private static String digits(String[] parts, Format format, boolean numeric) {
        boolean hyphen = !numeric && Boolean.TRUE.equals(format.hyphen);
        return String.join(hyphen ? "-" : "", parts);
    }
    private static String kana(String katakana, Format format) {
        if (format.hiragana) {
            StringBuilder out = new StringBuilder();
            for (char c : katakana.toCharArray())
                out.append(c >= 'ァ' && c <= 'ヶ' ? (char) (c - 0x60) : c);
            return out.toString();
        }
        return Boolean.FALSE.equals(format.fullWidth) ? toHalfWidthKana(katakana) : katakana;
    }
    private static String fits(String value, Format format) {
        return format.maxLength > 0 && value.codePointCount(0, value.length()) > format.maxLength
            ? null : value;
    }
    static String toFullWidth(String value) {
        StringBuilder out = new StringBuilder();
        for (char c : value.toCharArray()) {
            if (c == ' ') out.append('　');
            else if (c > ' ' && c <= '~') out.append((char) (c + 0xFEE0));
            else out.append(c);
        }
        return out.toString();
    }
    private static final Map<String, String> HALF_KANA = new HashMap<>();
    static {
        for (char h = 'ｦ'; h <= 'ﾝ'; h++) {
            String half = String.valueOf(h);
            HALF_KANA.put(Normalizer.normalize(half, Normalizer.Form.NFKC), half);
            for (String mark : new String[]{"ﾞ", "ﾟ"}) {
                String full = Normalizer.normalize(half + mark, Normalizer.Form.NFKC);
                if (full.length() == 1) HALF_KANA.put(full, half + mark);
            }
        }
        HALF_KANA.put("　", " ");
    }
    static String toHalfWidthKana(String value) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            String c = value.substring(i, i + 1);
            out.append(HALF_KANA.getOrDefault(c, c));
        }
        return out.toString();
    }
    private static Set<String> words(String... values) {
        Set<String> out = new HashSet<>();
        for (String value : values) out.add(fold(value));
        return out;
    }
    private static String fold(CharSequence value) {
        return Normalizer.normalize(value.toString(), Normalizer.Form.NFKC)
            .replaceAll("\\s", "").toLowerCase(Locale.ROOT);
    }
    private static final Pattern NUMBER = Pattern.compile("[0-9]+");
    private static final Pattern ERA = Pattern.compile("(令和|平成|昭和|大正|明治)([0-9]+|元)");
    /** Number an option stands for: 1990 for "1990年(平成2年)" or "平成2年", 4 for "04" / "4月". */
    private static int optionNumber(String option, boolean year) {
        Matcher western = NUMBER.matcher(option);
        List<Integer> numbers = new ArrayList<>();
        while (western.find() && western.group().length() <= 4) numbers.add(Integer.parseInt(western.group()));
        if (year) {
            for (int n : numbers) if (n >= 1800) return n;
            Matcher era = ERA.matcher(option);
            if (era.find()) return westernYear(era.group(1), era.group(2).equals("元") ? 1 : Integer.parseInt(era.group(2)));
            return -1;
        }
        if (numbers.isEmpty() && option.matches("元年?")) return 1;
        return numbers.size() == 1 ? numbers.get(0) : -1;
    }
    /** Index of the option naming the dummy value, matched on-device; -1 when absent. */
    public static int optionIndex(CharSequence[] options, Policy.Kind kind) {
        return optionIndex(options, kind, LocalDate.now());
    }
    public static int optionIndex(CharSequence[] options, Policy.Kind kind, LocalDate today) {
        if (options == null) return -1;
        String exact = null, loose = null;
        int number = -1;
        Set<String> synonyms = null;
        switch (kind) {
            case REGION: exact = REGION; loose = REGION.equals("北海道") ? REGION : REGION.replaceFirst("[都府県]$", ""); break;
            case CITY: exact = MUNICIPALITY + WARD; loose = WARD; break;
            case MUNICIPALITY: exact = MUNICIPALITY; break;
            case WARD: exact = WARD; break;
            case BIRTH_YEAR: number = BIRTH.getYear(); break;
            case BIRTH_MONTH: number = BIRTH.getMonthValue(); break;
            case BIRTH_DAY: number = BIRTH.getDayOfMonth(); break;
            case AGE: number = Period.between(BIRTH, today).getYears(); break;
            case BIRTH_ERA: synonyms = ERA_WORDS.get(eraName(BIRTH)); break;
            case BIRTH_ERA_YEAR: number = Integer.parseInt(eraYear(BIRTH).substring(2)); break;
            case JOB_TITLE: exact = JOB_TITLE; break;
            case GENDER: synonyms = GENDER_WORDS; break;
            case COUNTRY: synonyms = COUNTRY_WORDS; break;
            default: return -1;
        }
        int fallback = -1;
        for (int i = 0; i < options.length; i++) {
            if (options[i] == null) continue;
            String option = fold(options[i]);
            if (synonyms != null && synonyms.contains(option)) return i;
            if (exact != null && option.equals(fold(exact))) return i;
            if (loose != null && option.equals(fold(loose)) && fallback < 0) fallback = i;
            if (number >= 0 && optionNumber(option, kind == Policy.Kind.BIRTH_YEAR) == number) return i;
        }
        return fallback;
    }
    /** Whether a single radio/checkbox, identified by its own caption, is the one to select. */
    public static boolean toggleMatches(CharSequence caption, Policy.Kind kind) {
        return caption != null && kind == Policy.Kind.GENDER && GENDER_WORDS.contains(fold(caption));
    }
    /** Birth date for a native date control, as UTC midnight milliseconds. */
    public static long birthMillis() {
        return BIRTH.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli();
    }
    private Profile() {}
}
