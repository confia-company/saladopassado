"""Browser regressions; every HTTP request is fulfilled locally by the test."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ATTACK = '\"><img class="xss-probe" src="/missing" onerror="window.__xss=1"><svg onload="window.__xss=1"></svg>'


class FrontendSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.api = {}
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.__xss = 0;')
        self.page.route('**/*', self.route)
        self.page.goto('http://saladopassado.test/')
        self.page.wait_for_function("typeof renderQuestions === 'function' && typeof DOMPurify !== 'undefined'")

    def route(self, route):
        path = urlsplit(route.request.url).path
        if path in self.api:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps(self.api[path]))
        if path == '/':
            return route.fulfill(content_type='text/html', path=str(ROOT / 'templates/index.html'))
        if path.startswith('/static/'):
            file = (ROOT / path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT / 'static') and file.is_file():
                mime = 'text/css' if file.suffix == '.css' else 'application/javascript'
                return route.fulfill(content_type=mime, path=str(file))
        # No real service, CDN, account or credentials are used.
        return route.fulfill(status=401 if path == '/api/me' else 404, content_type='application/json', body='{}')

    def assert_no_execution(self):
        self.assertEqual(self.page.evaluate('window.__xss'), 0)
        self.assertEqual(self.errors, [])

    def test_external_text_and_attributes_cannot_create_markup(self):
        result = self.page.evaluate('''attack => {
            const encoded = escapeHtml(attack);
            renderTaskGrid(el.tasksGrid, [{id: attack, title: attack, description: encoded,
                answer_id: attack, questions_count: attack}], false);
            renderMatificGrid(el.matificAssignedGrid, [{title: attack, subtitle: attack,
                slug: attack, source: attack, completed: true, highest_score: attack, problem_count: attack}]);
            state.matificStats = {inventory: ['Body_Hair_' + attack], customization: {}};
            renderCustomizer();
            state.leiaspBooks = [{id: attack, title: attack, author: attack, level: attack,
                cover_url: '/cover?value=' + attack, progress: attack, total_pages: 10, current_page: attack}];
            renderLeiaSPBooks();
            state.activeTaskBatches = {test: {id: attack, total: attack, completed_count: attack, tasks: {}}};
            renderTasksBatchesBanners();
            const badge = document.createElement('div');
            badge.innerHTML = taskBatchBadgeHTML({status: 'completed', score: attack});
            document.body.appendChild(badge);
            showToast(attack, 'constructor');
            const roots = [el.tasksGrid, el.matificAssignedGrid, el.customizerSlotsGrid,
                el.leiaspGrid, el.tasksBatchesList, el.toastContainer, badge];
            return {
                probes: document.querySelectorAll('.xss-probe').length,
                active: roots.reduce((n, root) => n + root.querySelectorAll('[onerror], [onload], [onfocus]').length, 0),
                title: el.tasksGrid.querySelector('.task-title').textContent,
                attribute: el.tasksGrid.querySelector('.task-title').getAttribute('title'),
                description: el.tasksGrid.querySelector('.task-snippet').textContent,
                option: el.customizerSlotsGrid.querySelectorAll('option')[1].value,
                toast: el.toastContainer.querySelector('span').textContent,
                width: el.leiaspGrid.querySelector('.progress-bar-bg > div').style.width,
            };
        }''', ATTACK)
        self.assertEqual(result['probes'], 0)
        self.assertEqual(result['active'], 0)
        for field in ('title', 'attribute', 'description', 'toast'):
            self.assertEqual(result[field], ATTACK)
        self.assertEqual(result['option'], 'Body_Hair_' + ATTACK)
        self.assertEqual(result['width'], '0%')
        self.assert_no_execution()

    def test_questions_keep_content_and_remove_active_html(self):
        result = self.page.evaluate('''attack => {
            const rich = '<p><strong>Enunciado</strong> H<sub>2</sub>O</p>' +
                '<img src="https://example.test/figure.png" alt="Figura">' +
                '<table><tr><td>Dado</td></tr></table><a href="https://example.test/source">Fonte</a>' +
                '<img src="/missing" onerror="window.__xss=1">' +
                '<script>window.__xss=1</script><iframe srcdoc="<script>parent.__xss=1</script>"></iframe>' +
                '<svg onload="window.__xss=1"></svg><a href="javascript:window.__xss=1">Link</a>' +
                '<span id="view-auth" data-stop-batch="bad" style="position:fixed" onclick="window.__xss=1">Texto</span>';
            renderQuestions([
                {id: 'info', type: 'info', statement: rich},
                {id: attack, type: 'single', statement: rich, options: {[attack]: {text: escapeHtml(attack)}}},
                {id: 'text', type: 'text', statement: rich, options: {max_text_count: attack}},
                {id: 'text-ai', type: 'text_ai', statement: rich},
                {id: 'type', type: attack, statement: 'Texto', options: []},
            ]);
            const root = el.questionsContainer;
            return {
                dangerous: root.querySelectorAll('script, iframe, svg, [onerror], [onload], [onclick], [style], [data-stop-batch]').length,
                javascriptLinks: [...root.querySelectorAll('a')].filter(a => a.protocol === 'javascript:').length,
                bold: root.querySelector('strong').textContent,
                image: root.querySelector('img').getAttribute('src'),
                cell: root.querySelector('td').textContent,
                link: root.querySelector('a').href,
                options: root.querySelectorAll('.option-row').length,
                text: root.querySelector('.option-text').textContent,
                textarea: root.querySelector('textarea').getAttribute('maxlength'),
                clobbers: root.querySelectorAll('#view-auth').length,
            };
        }''', ATTACK)
        self.assertEqual(result['dangerous'], 0)
        self.assertEqual(result['javascriptLinks'], 0)
        self.assertEqual(result['clobbers'], 0)
        self.assertEqual(result['bold'], 'Enunciado')
        self.assertEqual(result['image'], 'https://example.test/figure.png')
        self.assertEqual(result['cell'], 'Dado')
        self.assertEqual(result['link'], 'https://example.test/source')
        self.assertEqual(result['options'], 1)
        self.assertEqual(result['text'], ATTACK)
        self.assertEqual(result['textarea'], ATTACK)
        self.assert_no_execution()

    def test_missing_sanitizer_falls_back_to_text(self):
        result = self.page.evaluate('''attack => {
            window.DOMPurify = undefined;
            renderQuestions([{id: 1, type: 'info', statement: attack}]);
            return {html: el.questionsContainer.querySelector('.question-statement').innerHTML,
                text: el.questionsContainer.querySelector('.question-statement').textContent,
                images: el.questionsContainer.querySelectorAll('img, svg').length};
        }''', ATTACK)
        self.assertEqual(result['text'], ATTACK)
        self.assertEqual(result['images'], 0)
        self.assertIn('&lt;', result['html'])
        self.assert_no_execution()

    def test_cover_urls_reject_active_protocols(self):
        for url in ('javascript:window.__xss=1', 'data:image/svg+xml,<svg onload="window.__xss=1"/>', 'vbscript:msgbox(1)'):
            with self.subTest(url=url):
                result = self.page.evaluate('''url => {
                    state.leiaspBooks = [{id: 1, title: 'Livro', cover_url: url}];
                    renderLeiaSPBooks();
                    renderActiveLeiaSPBanner({book_title: 'Livro', book_cover_url: url});
                    return {covers: el.leiaspGrid.querySelectorAll('img').length,
                        banner: el.activeBannerCover.style.display};
                }''', url)
                self.assertEqual(result['covers'], 0)
                self.assertEqual(result['banner'], 'none')
        self.assert_no_execution()

    def test_all_job_pollers_render_logs_as_text(self):
        job = {'status': 'running', 'logs': [ATTACK], 'completed_count': 0, 'total_count': 1}
        self.api.update({
            '/api/matific/job/test': job,
            '/api/matific/batch/status': job,
            '/api/leiasp/job/test': {'job': job},
        })
        self.page.evaluate("startMatificJobPolling('test'); pollMatificBatch(); pollLeiaSPJob('test');")
        self.page.wait_for_function('''attack => [el.matificSimLogs, el.batchTerminalLogs, el.leiaspLogsBox]
            .every(root => root.querySelector('.log-line')?.textContent === attack)''', arg=ATTACK)
        result = self.page.evaluate('''() => [el.matificSimLogs, el.batchTerminalLogs, el.leiaspLogsBox]
            .map(root => ({text: root.querySelector('.log-line').textContent, images: root.querySelectorAll('img, svg').length}))''')
        for log in result:
            self.assertEqual(log['text'], ATTACK)
            self.assertEqual(log['images'], 0)
        self.assert_no_execution()

    def test_task_modal_escapes_decoded_description(self):
        self.api['/api/task/1'] = {'title': 'Tarefa', 'description': ATTACK.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), 'questions': []}
        self.page.evaluate('openTaskModal(1, false)')
        self.assertEqual(self.page.locator('#task-description').text_content(), ATTACK)
        self.assertEqual(self.page.locator('#task-description img, #task-description svg').count(), 0)
        self.assert_no_execution()


if __name__ == '__main__':
    unittest.main()
