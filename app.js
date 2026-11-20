'use strict';

if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const reveal = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      reveal.unobserve(entry.target);
      entry.target.classList.add('reveal');
      entry.target.addEventListener('animationend', () => entry.target.classList.remove('reveal'), {once: true});
    }
  }, {rootMargin: '0px 0px -24px 0px'});
  document.querySelectorAll('main > .masthead, main > section').forEach((section) => reveal.observe(section));
}

const get = (id) => document.getElementById(id);
const tbody = get('rows');
let revision = 0;

async function post(path, body, type) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': type}, body});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '操作失败。');
  return data;
}

function status(id, message, error = false) {
  get(id).textContent = message;
  get(id).classList.toggle('error', error);
}

function invalidate() {
  const hadResult = get('credits').textContent !== '—';
  revision += 1;
  for (const id of ['gpa', 'average', 'credits']) get(id).textContent = '—';
  for (const row of tbody.rows) {
    for (const cell of [...row.cells].slice(4, 7)) cell.textContent = '—';
    row.classList.remove('invalid');
  }
  if (hadResult) status('calc-status', '课程已修改，请重新计算。');
}

function updateEmpty() {
  get('empty').hidden = tbody.rows.length > 0;
  get('portal-calc-note').hidden = !tbody.querySelector('tr[data-source="portal"]');
}

function addCourse(data = {}, focus = false) {
  const row = tbody.insertRow();
  if (data.source === 'portal') row.dataset.source = 'portal';
  const fields = [['name', '课程名称'], ['credits', '学分'], ['grade', '成绩'], ['mode', '修读方式']];
  for (const [key, label] of fields) {
    const control = document.createElement(key === 'mode' ? 'select' : 'input');
    control.name = key;
    control.setAttribute('aria-label', label);
    if (key === 'mode') {
      for (const mode of ['', '正常', '补考', '重修']) control.add(new Option(mode || '待确认', mode));
    }
    if (key === 'credits') control.inputMode = 'decimal';
    control.value = data[key] ?? (key === 'mode' ? '正常' : '');
    row.insertCell().append(control);
  }
  for (let index = 0; index < 3; index += 1) row.insertCell().textContent = '—';
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'remove';
  remove.textContent = '删除';
  remove.addEventListener('click', () => { row.remove(); updateEmpty(); invalidate(); });
  row.insertCell().append(remove);
  if (focus) row.cells[0].firstChild.focus();
}

get('add')?.addEventListener('click', () => { addCourse({}, true); updateEmpty(); invalidate(); });
tbody.addEventListener('input', invalidate);

get('import-text').addEventListener('click', async () => {
  const content = get('portal-text').value.trim();
  get('portal-raw-box').hidden = true;
  if (!content) {
    status('portal-status', '请先粘贴「全部及格成绩」页面。', true);
    return;
  }
  get('import-text').disabled = true;
  try {
    const result = await post('/api/portal/text', content, 'text/plain; charset=utf-8');
    get('portal-raw').textContent = result.unmatched.join('\n');
    get('portal-raw-box').hidden = !result.unmatched.length;
    if (!result.rows.length) {
      status('portal-status', '没有找到课程。请完整复制含表头和课程行的页面。', true);
      return;
    }
    for (const course of result.rows) addCourse(course);
    invalidate();
    updateEmpty();
    status('portal-status', [
      `已添加 ${result.rows.length} 门，修读方式默认设为「正常」，可在课程表中核对修改。`,
      result.unmatched.length ? `${result.unmatched.length} 行未导入。` : '',
      ...result.notices,
    ].filter(Boolean).join(' '));
  } catch (error) {
    status('portal-status', error.message, true);
  } finally {
    get('import-text').disabled = false;
  }
});

get('calculate').addEventListener('click', async () => {
  const button = get('calculate');
  button.disabled = true;
  const current = revision;
  const rows = [...tbody.rows].map((row) => ({
    ...Object.fromEntries([...row.querySelectorAll('input,select')].map((control) => [control.name, control.value])),
    source: row.dataset.source,
  }));
  try {
    const result = await post('/api/calculate', JSON.stringify(rows), 'application/json');
    if (current !== revision) return;
    result.details.forEach((detail, index) => {
      const row = tbody.rows[index];
      row.cells[4].textContent = detail.points ?? '—';
      row.cells[5].textContent = detail.weighted ?? '—';
      row.cells[6].textContent = detail.errors.join('；') || detail.status;
      row.classList.toggle('invalid', detail.errors.length > 0);
    });
    if (result.invalid) {
      status('calc-status', `还有 ${result.invalid} 行待修正。修正后重新计算。`, true);
      return;
    }
    get('gpa').textContent = result.gpa ?? '—';
    get('average').textContent = result.average ?? '—';
    get('credits').textContent = result.credits;
    const noGpa = result.gpa === null ? '没有可用于 GPA 的正学分。' : '';
    const noAverage = result.gpa !== null && result.average === null
      ? '实际 GPA 不在 1–4 的换算范围内，无法换算百分制成绩。' : '';
    status('calc-status', `已排除 ${result.excluded} 条四六级记录。${noGpa}${noAverage}`);
  } catch (error) {
    status('calc-status', error.message, true);
  } finally {
    button.disabled = false;
  }
});
