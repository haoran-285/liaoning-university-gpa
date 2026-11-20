import re
import unicodedata
from decimal import Decimal


POINTS = tuple(map(Decimal, '''
1.00 1.07 1.15 1.22 1.29 1.36 1.43 1.50 1.57 1.64 1.70 1.77 1.83 1.90 1.96 2.02 2.08 2.14 2.20 2.26
2.31 2.37 2.42 2.48 2.53 2.58 2.63 2.68 2.73 2.78 2.83 2.87 2.92 2.96 3.01 3.05 3.09 3.13 3.17 3.21
3.25 3.29 3.32 3.36 3.39 3.43 3.46 3.49 3.52 3.55 3.58 3.61 3.63 3.66 3.68 3.71 3.73 3.75 3.77 3.79
3.81 3.83 3.85 3.86 3.88 3.89 3.91 3.92 3.93 3.94 3.95 3.96 3.97 3.98 3.98 3.99 3.99 4.00 4.00 4.00
4.00'''.split()))
FIVE_LEVELS = {'优秀': Decimal(4), '良好': Decimal(3), '中等': Decimal(2),
               '及格': Decimal(1), '不及格': Decimal(0)}
TWO_LEVELS = {'合格': Decimal(3), '不合格': Decimal(0)}
LEVELS = FIVE_LEVELS | TWO_LEVELS
MODES = ('正常', '补考', '重修')
EXAM = re.compile(r'(?:全国)?(?:大学)?英语[四六46]级(?:考试)?|cet-?[46]', re.I)


def clean(value):
    return unicodedata.normalize('NFKC', str(value if value is not None else '')).strip()


def number(value):
    return Decimal(value) if re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,6})?', value) else None


def portal_unsupported(grade, mode=None):
    score = number(clean(grade))
    return (clean(mode) in ('补考', '重修')
            or bool(re.search(r'补考|重修|不及格|不合格', clean(grade)))
            or (score is not None and score < 60))


def calculate(rows):
    details = []
    total = points_sum = Decimal(0)
    invalid = excluded = 0
    for row in rows:
        name, credits_text, grade, mode = (clean(row.get(key)) for key in ('name', 'credits', 'grade', 'mode'))
        name_key = re.sub(r'[\s()·]', '', name)
        detail = {'points': None, 'weighted': None, 'status': '计入', 'errors': []}
        details.append(detail)
        if EXAM.fullmatch(name_key):
            detail['status'] = '四六级排除'
            excluded += 1
            continue
        credits = number(credits_text)
        score = number(grade)
        level = LEVELS.get(grade)
        errors = detail['errors']
        if row.get('source') == 'portal' and portal_unsupported(grade):
            errors.append('教务导入行须填写及格成绩；不及格课程请手动添加')
        if not name:
            errors.append('缺少课程名称')
        if credits is None or credits > 100:
            errors.append('学分须为 0–100 的数字')
        if level is None and (score is None or score > 100):
            errors.append('成绩须为 0–100 的数字或已知等级')
        if mode not in MODES:
            errors.append('请选择修读方式')
        if score is not None and 60 <= score <= 100 and mode == '正常' and score * 2 % 1:
            errors.append('正常成绩须匹配对照表的 0.5 分步长')
        if errors:
            detail['status'] = '待修正'
            invalid += 1
            continue
        if level is not None:
            points = min(level, Decimal(1)) if mode != '正常' else level
        elif score < 60:
            points = Decimal(0)
        elif mode != '正常':
            points = Decimal(1)
        else:
            points = POINTS[int((score - 60) * 2)]
        total += credits
        weighted = points * credits
        points_sum += weighted
        detail.update(points=f'{points:.2f}', weighted=format(weighted.normalize(), 'f'))
    gpa = points_sum / total if total else None
    # The inverse is defined only for scores from 60 to 100. Check before display rounding.
    average = Decimal(100) - (1600 * (4 - gpa) / 3).sqrt() if gpa is not None and 1 <= gpa <= 4 else None
    return {
        'details': details, 'invalid': invalid, 'excluded': excluded,
        'credits': format(total.normalize(), 'f'),
        'gpa': f'{gpa:.4f}' if gpa is not None else None,
        'average': f'{average:.3f}' if average is not None else None,
    }
