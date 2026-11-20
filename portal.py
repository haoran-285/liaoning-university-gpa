import re

from gpa import clean, portal_unsupported


FIELD_NAMES = {'课程名': 'name', '课程名称': 'name', '学分': 'credits', '成绩': 'grade'}
UNSUPPORTED = '请粘贴「全部及格成绩」页面。其他考核记录可手动补录。'


def portal_result(rows, unmatched, notices=()):
    if any(portal_unsupported(row['grade'], row.get('mode')) for row in rows):
        raise ValueError(UNSUPPORTED)
    for row in rows:
        row.update(mode='正常', source='portal')
    return {'rows': rows, 'unmatched': unmatched, 'notices': list(notices)}


def parse_portal_text(text):
    rows, unmatched, notices = [], [], []
    columns = None
    for raw in text.splitlines():
        line = clean(raw).removeprefix('&#x20;').strip().rstrip('\\')
        fields = line.split('\t')
        if len(fields) == 1:
            fields = re.split(r'\s{2,}', line)
        if len(fields) == 1:
            fields = line.split()
        fields = [clean(field) for field in fields]
        summary = re.search(r'已修\s*(\d+)\s*门.*?通过\s*(\d+)\s*门', line)
        if summary:
            columns = None
            if summary[1] != summary[2]:
                notice = '有学期的已修门数与通过门数不同，请核对是否有未显示的课程。仅按导入行计算。'
                if notice not in notices:
                    notices.append(notice)
            continue
        if fields and fields[0] == '序号':
            columns = {FIELD_NAMES[field]: index for index, field in enumerate(fields) if field in FIELD_NAMES}
            if set(columns) != set(FIELD_NAMES.values()):
                columns = None
            continue
        if not columns or not fields or not re.fullmatch(r'\d+', fields[0]):
            continue
        if any(re.fullmatch(r'补考(?:及格|通过)?|重修(?:及格|通过)?', field) for field in fields[1:]):
            raise ValueError(UNSUPPORTED)
        if len(fields) <= max(columns.values()):
            unmatched.append(raw)
            continue
        row = {key: fields[index] for key, index in columns.items()}
        if not all(row.values()):
            unmatched.append(raw)
            continue
        rows.append(row)
    return portal_result(rows, unmatched, notices)
