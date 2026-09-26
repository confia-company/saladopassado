// Use for text and quoted HTML attributes in templates, never raw HTML or CSS.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

// Task statements need formatting and images. Keep a small set of content
// elements, excluding active content, inline styles and application attributes.
function sanitizeHtml(value) {
  if (!window.DOMPurify || !window.DOMPurify.isSupported) return escapeHtml(value);
  return window.DOMPurify.sanitize(String(value ?? ''), {
    ALLOWED_TAGS: [
      'p', 'br', 'div', 'span', 'b', 'strong', 'i', 'em', 'u', 's', 'small',
      'sub', 'sup', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
      'blockquote', 'pre', 'code', 'hr', 'table', 'caption', 'thead', 'tbody',
      'tfoot', 'tr', 'th', 'td', 'a', 'img', 'figure', 'figcaption',
      'audio', 'video', 'source',
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'width', 'height', 'colspan', 'rowspan',
      'start', 'controls', 'type',
    ],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
  });
}

function safeImageUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return '';
  try {
    const url = new URL(value, window.location.href);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function renderLogLines(container, logs) {
  const fragment = document.createDocumentFragment();
  for (const message of logs) {
    const line = document.createElement('div');
    line.className = 'log-line';
    line.textContent = String(message ?? '');
    fragment.appendChild(line);
  }
  container.replaceChildren(fragment);
}
