"""Field kinds an annotator can assign.

The names and masks mirror ``KIND_MASKS`` in the Chrome extension's ``jev-kinds.ts`` so that
labels compare directly with classifier output. ``OTHER`` is the ground-truth answer for a field
that is not a profile field and should stay empty; it shares mask 0 with the classifier's
``UNKNOWN``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

OTHER: Final = "OTHER"
UNKNOWN: Final = "UNKNOWN"

_REGION: Final = 1
_MUNICIPALITY: Final = 1 << 1
_WARD: Final = 1 << 2
_TOWN: Final = 1 << 3
_CHOME: Final = 1 << 4
_BAN: Final = 1 << 5
_GO: Final = 1 << 6
_BUILDING: Final = 1 << 7
_CITY: Final = _MUNICIPALITY | _WARD
_BLOCK: Final = _CHOME | _BAN | _GO
_MOBILE: Final = 1 << 30


@dataclass(frozen=True, slots=True)
class Kind:
    """One assignable kind.

    Attributes:
        name: Identifier shared with the classifiers.
        mask: Profile components the kind renders; equal masks are the same answer.
        group: Heading the picker lists the kind under.
        label: Short Japanese description shown to the annotator.
    """

    name: str
    mask: int
    group: str
    label: str


KINDS: Final[tuple[Kind, ...]] = (
    Kind("FAMILY", 1 << 8, "氏名", "姓"),
    Kind("GIVEN", 1 << 9, "氏名", "名"),
    Kind("FULL_NAME", (1 << 8) | (1 << 9), "氏名", "氏名（姓名を1欄）"),
    Kind("FAMILY_KANA", 1 << 10, "氏名", "セイ（姓のフリガナ）"),
    Kind("GIVEN_KANA", 1 << 11, "氏名", "メイ（名のフリガナ）"),
    Kind("FULL_KANA", (1 << 10) | (1 << 11), "氏名", "フリガナ（姓名を1欄）"),
    Kind("POSTAL", (1 << 12) | (1 << 13), "郵便番号", "郵便番号（7桁を1欄）"),
    Kind("POSTAL_1", 1 << 12, "郵便番号", "郵便番号 前3桁"),
    Kind("POSTAL_2", 1 << 13, "郵便番号", "郵便番号 後4桁"),
    Kind("REGION", _REGION, "住所", "都道府県"),
    Kind("MUNICIPALITY", _MUNICIPALITY, "住所", "市・郡"),
    Kind("WARD", _WARD, "住所", "区・町村"),
    Kind("CITY", _CITY, "住所", "市区町村"),
    Kind("TOWN", _TOWN, "住所", "町名"),
    Kind("CHOME", _CHOME, "住所", "丁目"),
    Kind("BAN", _BAN, "住所", "番"),
    Kind("GO", _GO, "住所", "号"),
    Kind("BAN_GO", _BAN | _GO, "住所", "番＋号"),
    Kind("BLOCK", _BLOCK, "住所", "番地（丁目・番・号）"),
    Kind("TOWN_CHOME", _TOWN | _CHOME, "住所", "町名＋丁目"),
    Kind("STREET", _TOWN | _BLOCK, "住所", "町名＋番地"),
    Kind("BUILDING", _BUILDING, "住所", "建物名・部屋番号"),
    Kind("REGION_CITY", _REGION | _CITY, "住所", "都道府県＋市区町村"),
    Kind("CITY_TOWN", _CITY | _TOWN, "住所", "市区町村＋町名"),
    Kind("CITY_STREET", _CITY | _TOWN | _BLOCK, "住所", "市区町村＋町名番地"),
    Kind("WARD_STREET", _WARD | _TOWN | _BLOCK, "住所", "区町村＋町名番地"),
    Kind("ADDRESS_LINES", _TOWN | _BLOCK | _BUILDING, "住所", "町名番地＋建物"),
    Kind(
        "AFTER_MUNICIPALITY", _WARD | _TOWN | _BLOCK | _BUILDING, "住所", "区町村以降（建物まで）"
    ),
    Kind(
        "ADDRESS_AFTER_REGION", _CITY | _TOWN | _BLOCK | _BUILDING, "住所", "都道府県より後すべて"
    ),
    Kind("ADDRESS_NO_BUILDING", _REGION | _CITY | _TOWN | _BLOCK, "住所", "住所（建物を除く）"),
    Kind("ADDRESS_FULL", _REGION | _CITY | _TOWN | _BLOCK | _BUILDING, "住所", "住所すべて"),
    Kind("PHONE", (1 << 14) | (1 << 15) | (1 << 16), "電話", "電話番号（固定・区別なし、1欄）"),
    Kind("PHONE_1", 1 << 14, "電話", "電話 1つ目（市外局番）"),
    Kind("PHONE_2", 1 << 15, "電話", "電話 2つ目"),
    Kind("PHONE_3", 1 << 16, "電話", "電話 3つ目"),
    Kind("MOBILE", (1 << 14) | (1 << 15) | (1 << 16) | _MOBILE, "電話", "携帯電話（1欄）"),
    Kind("MOBILE_1", (1 << 14) | _MOBILE, "電話", "携帯 1つ目"),
    Kind("MOBILE_2", (1 << 15) | _MOBILE, "電話", "携帯 2つ目"),
    Kind("MOBILE_3", (1 << 16) | _MOBILE, "電話", "携帯 3つ目"),
    Kind("BIRTHDATE", (1 << 23) | (1 << 24) | (1 << 25) | (1 << 26), "生年月日", "生年月日（1欄）"),
    Kind("BIRTH_YEAR", 1 << 24, "生年月日", "生年（西暦または元号付き）"),
    Kind("BIRTH_MONTH", 1 << 25, "生年月日", "生月"),
    Kind("BIRTH_DAY", 1 << 26, "生年月日", "生日"),
    Kind("BIRTH_ERA", 1 << 23, "生年月日", "元号（別欄）"),
    Kind("BIRTH_ERA_YEAR", 1 << 24, "生年月日", "元号内の年（元号が別欄）"),
    Kind("GENDER", 1 << 27, "属性", "性別"),
    Kind("AGE", 1 << 28, "属性", "年齢"),
    Kind("COUNTRY", 1 << 29, "属性", "国・地域"),
    Kind("COMPANY", 1 << 17, "勤務先", "会社名・勤務先"),
    Kind("DEPARTMENT", 1 << 18, "勤務先", "部署"),
    Kind("JOB_TITLE", 1 << 19, "勤務先", "役職"),
    Kind("EMAIL", 1 << 20, "アカウント", "メールアドレス（確認用も）"),
    Kind("USERNAME", 1 << 21, "アカウント", "ユーザー名・ログインID"),
    Kind("PASSWORD", 1 << 22, "アカウント", "パスワード（確認用も）"),
    Kind(OTHER, 0, "対象外", "プロフィール以外（空のままが正解）"),
)

BY_NAME: Final[dict[str, Kind]] = {kind.name: kind for kind in KINDS}


def mask_of(name: str) -> int:
    """Return the component mask of a label or classifier kind.

    Raises:
        ValueError: If ``name`` is neither a known kind nor ``UNKNOWN``.
    """
    if name == UNKNOWN:
        return 0
    kind = BY_NAME.get(name)
    if kind is None:
        msg = f"unknown kind: {name!r}"
        raise ValueError(msg)
    return kind.mask


def same_answer(label: str, predicted: str) -> bool:
    """Whether a prediction fills a field with the same components as the label."""
    return mask_of(label) == mask_of(predicted)
