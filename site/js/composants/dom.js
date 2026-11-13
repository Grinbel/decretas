/**
 * Safe DOM building. Every string that reaches the page goes through textContent or
 * setAttribute: nothing in this site ever writes HTML from a string, so a name read in an
 * archive file can never become markup.
 */

const SVG_NS = 'http://www.w3.org/2000/svg';
const URL_ATTRIBUTES = new Set(['href', 'src', 'action', 'formaction', 'poster']);

function ajouter(parent, child) {
  if (child === null || child === undefined || child === false) return;
  if (Array.isArray(child)) {
    for (const c of child) ajouter(parent, c);
    return;
  }
  parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
}

/** An address the page may put in href/src: same-site hash or path, or http(s). */
export function adresseAdmise(value) {
  const s = String(value);
  if (s.startsWith('#') || /^[a-z0-9_./-]+$/i.test(s)) return true;
  return /^https?:\/\//i.test(s);
}

/**
 * h('p', { class: 'x', on: { click: fn }, aria: { live: 'polite' }, data: { cle: 'k' } }, 'text', node, [more])
 * Attributes with a null, undefined or false value are left out; true gives an empty attribute.
 * @param {string} tag
 * @param {Object|null} [attrs]
 * @param {...(Node|string|number|null|undefined|false|Array)} children
 * @returns {HTMLElement}
 */
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === 'on') {
      for (const [type, handler] of Object.entries(value)) el.addEventListener(type, handler);
    } else if (name === 'aria') {
      for (const [k, v] of Object.entries(value)) if (v !== null && v !== undefined) el.setAttribute(`aria-${k}`, String(v));
    } else if (name === 'data') {
      for (const [k, v] of Object.entries(value)) if (v !== null && v !== undefined) el.dataset[k] = String(v);
    } else if (name.startsWith('on')) {
      throw new TypeError('Event handlers go in "on": {…}, never in an attribute.');
    } else if (URL_ATTRIBUTES.has(name)) {
      if (!adresseAdmise(value)) throw new TypeError(`Refused address in ${name}.`);
      el.setAttribute(name, String(value));
    } else {
      el.setAttribute(name, value === true ? '' : String(value));
    }
  }
  ajouter(el, children);
  return el;
}

/** Remove every child of an element. */
export function vider(el) {
  el.replaceChildren();
  return el;
}

/** Replace the children of an element. */
export function remplacer(el, ...children) {
  el.replaceChildren();
  ajouter(el, children);
  return el;
}

// Icons: drawn here, one stroke weight, 24 px grid. No emoji, no icon font, no external file.
const TRACES = {
  fleche: ['M5 12h14', 'M13 6l6 6-6 6'],
  externe: ['M14 5h5v5', 'M19 5l-8 8', 'M11 7H6v11h11v-5'],
  attention: ['M12 4l9 16H3z', 'M12 10v4', 'M12 17v.5'],
  info: ['M12 3a9 9 0 100 18 9 9 0 000-18z', 'M12 11v5', 'M12 7.5v.5'],
  imprimer: ['M7 9V4h10v5', 'M7 17H4v-7h16v7h-3', 'M7 14h10v6H7z'],
  retour: ['M19 12H5', 'M11 6l-6 6 6 6'],
  image: ['M4 5h16v14H4z', 'M4 16l5-5 4 4 3-3 4 4', 'M15.5 9.5v.01'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  lien: ['M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1', 'M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1'],
  loupe: ['M10.5 4a6.5 6.5 0 100 13 6.5 6.5 0 000-13z', 'M15.5 15.5L20 20'],
  coche: ['M5 12.5l4.5 4.5L19 7.5'],
  suivant: ['M9 6l6 6-6 6'],
  precedent: ['M15 6l-6 6 6 6'],
};

/**
 * A decorative icon (hidden from assistive technology: the text next to it says the thing).
 * @param {keyof typeof TRACES} nom
 * @returns {SVGElement}
 */
export function icone(nom) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', 'icone');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  for (const d of TRACES[nom] ?? []) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}

/** Arabic script present? Such text is marked lang="ar" dir="rtl" wherever it is shown. */
export function estArabe(text) {
  return /[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]/.test(String(text ?? ''));
}

/** A span for a typed or written name, with the right language and direction when Arabic. */
export function nomEcrit(text, attrs) {
  const arabic = estArabe(text);
  return h('span', { ...(attrs ?? {}), lang: arabic ? 'ar' : null, dir: arabic ? 'rtl' : null }, text);
}

const ARABE_RE = /[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]+(?:[\s\u0640]+[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]+)*/g;

/**
 * A sentence of ours that quotes what was typed: the Arabic runs are wrapped in
 * <span lang="ar" dir="rtl">, the rest stays text. Returns nodes for h().
 * @param {string} text
 * @returns {Array<string|HTMLElement>}
 */
export function texteMixte(text) {
  const s = String(text ?? '');
  const out = [];
  let cursor = 0;
  for (const m of s.matchAll(ARABE_RE)) {
    if (m.index > cursor) out.push(s.slice(cursor, m.index));
    out.push(h('span', { lang: 'ar', dir: 'rtl' }, m[0]));
    cursor = m.index + m[0].length;
  }
  if (cursor < s.length) out.push(s.slice(cursor));
  return out;
}

/**
 * Move the focus to a heading (made focusable). The page scrolls only when the heading is out
 * of view: a title already on screen stays where it is, and so does the site header above it.
 */
export function viserTitre(el) {
  if (!el) return;
  el.setAttribute('tabindex', '-1');
  el.focus({ preventScroll: true });
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.bottom > window.innerHeight) el.scrollIntoView({ block: 'start', behavior: 'auto' });
}
