/*
 * Watches the start of the page. A classic script on purpose (ES5, no module): it must run in
 * every browser, including one that cannot run the modules of the site at all.
 *
 *   - a browser without ES modules: says so at once, instead of a blank page;
 *   - a module that cannot be fetched (bad network, a file missing): says so, with what to do;
 *   - nothing ready after 15 seconds: says that the page is slow, and what to do if it stays so.
 *
 * js/app.js marks the page ready (<html data-pret>) when it starts, and replaces the first
 * screen of index.html. The sentences are in index.html, next to the first screen (data-*).
 * Text is written with textContent only.
 */
(function () {
  'use strict';
  var racine = document.documentElement;
  racine.setAttribute('data-js', '');

  function dire(cle) {
    if (racine.hasAttribute('data-pret')) return;
    var etat = document.querySelector('.demarrage__etat');
    if (!etat) return;
    var texte = etat.getAttribute('data-' + cle);
    if (texte) {
      etat.textContent = texte;
      etat.setAttribute('data-alerte', cle);
    }
  }

  var script = document.createElement('script');
  if (!('noModule' in script)) {
    // This browser ignores <script type="module">: nothing else will ever run.
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { dire('ancien'); });
    else dire('ancien');
    return;
  }

  // A module that fails to download or to parse fires "error" on the page's module script.
  window.addEventListener('error', function (event) {
    var cible = event.target;
    if (cible && cible.tagName === 'SCRIPT' && cible.getAttribute('type') === 'module') dire('echec');
  }, true);

  window.setTimeout(function () { dire('lent'); }, 15000);
}());
