/**
 * Main-thread side of the data worker (donnees/service.js documents the messages).
 * The page never touches the big files: it asks this client, which answers with promises.
 *
 *   const donnees = creerClientDonnees();
 *   donnees.abonner((etat) => …)       etat: {phase, progression, resume, erreur}
 *   donnees.charger()                  idempotent; resolves with the "resume" when the index is ready
 *   donnees.chercher(etatDeRecherche)  -> {correspondances, fiches, bilan, apparentees, fidele}
 *   donnees.fiche(ref)                 -> a fiche, or null
 *   donnees.decretsAn(filtre)          -> decrees of the Archives nationales index
 *   donnees.reessayer()                after an error: start again with a new worker
 */

export class ErreurDonnees extends Error {
  constructor(code, detail = {}) {
    super(`Data error: ${code}`);
    this.name = 'ErreurDonnees';
    this.code = code;
    this.fichier = detail.fichier ?? null;
    this.statut = detail.statut ?? null;
  }
}

/**
 * @param {{creerWorker?: () => Worker}} [options]
 */
export function creerClientDonnees({ creerWorker = () => new Worker('js/donnees/worker.js', { type: 'module' }) } = {}) {
  /** @type {{phase: 'repos'|'chargement'|'pret'|'erreur', progression: Object|null, resume: Object|null, erreur: ErreurDonnees|null}} */
  let etat = { phase: 'repos', progression: null, resume: null, erreur: null };
  const abonnes = new Set();
  const attentes = new Map();
  let worker = null;
  let chargement = null;
  let prochainId = 1;

  const publier = (patch) => {
    etat = { ...etat, ...patch };
    for (const fn of abonnes) fn(etat);
  };

  function echouerTout(error) {
    for (const { reject } of attentes.values()) reject(error);
    attentes.clear();
  }

  function demarrer() {
    let resolveLoad;
    let rejectLoad;
    chargement = new Promise((resolve, reject) => {
      resolveLoad = resolve;
      rejectLoad = reject;
    });
    chargement.catch(() => {}); // callers that do not wait must not raise an unhandled rejection
    try {
      worker = creerWorker();
    } catch (cause) {
      const error = new ErreurDonnees('worker');
      publier({ phase: 'erreur', erreur: error, progression: null });
      rejectLoad(error);
      return;
    }
    worker.onmessage = (event) => {
      const m = event.data ?? {};
      if (m.type === 'progression') {
        publier({ phase: 'chargement', progression: { etape: m.etape, recus: m.recus, total: m.total } });
      } else if (m.type === 'pret') {
        publier({ phase: 'pret', resume: m.resume, progression: null, erreur: null });
        resolveLoad(m.resume);
      } else if (m.type === 'erreur') {
        const error = new ErreurDonnees(m.code, m);
        if (m.id !== undefined && attentes.has(m.id)) {
          attentes.get(m.id).reject(error);
          attentes.delete(m.id);
        } else if (etat.phase !== 'pret') {
          publier({ phase: 'erreur', erreur: error, progression: null });
          rejectLoad(error);
          echouerTout(error);
        }
      } else if (m.id !== undefined && attentes.has(m.id)) {
        attentes.get(m.id).resolve(m);
        attentes.delete(m.id);
      }
    };
    worker.onerror = (event) => {
      event.preventDefault?.();
      const error = new ErreurDonnees('worker');
      if (etat.phase !== 'pret') {
        publier({ phase: 'erreur', erreur: error, progression: null });
        rejectLoad(error);
      }
      echouerTout(error);
    };
    publier({ phase: 'chargement', progression: { etape: 'telechargement', recus: 0, total: null }, erreur: null });
    worker.postMessage({ type: 'charger', base: document.baseURI });
  }

  /** Drop a failed worker, so that the next caller starts the download again. */
  function oublierEchec() {
    worker?.terminate();
    worker = null;
    chargement = null;
  }

  function charger() {
    // A failed load is never kept: whoever asks next (a search, a retry button) tries again.
    if (etat.phase === 'erreur') oublierEchec();
    if (chargement === null) demarrer();
    return chargement;
  }

  async function demander(message) {
    await charger();
    return new Promise((resolve, reject) => {
      const id = prochainId++;
      attentes.set(id, { resolve, reject });
      worker.postMessage({ ...message, id });
    });
  }

  return {
    etat: () => etat,
    /** Subscribe to state changes; returns the function that unsubscribes. */
    abonner(fn) {
      abonnes.add(fn);
      return () => abonnes.delete(fn);
    },
    charger,
    reessayer() {
      oublierEchec();
      echouerTout(new ErreurDonnees('abandon'));
      return charger();
    },
    chercher: (etatDeRecherche, limite) => demander({ type: 'chercher', etat: etatDeRecherche, limite }),
    fiche: (ref) => demander({ type: 'fiche', ref }).then((m) => m.fiche),
    decretsAn: (filtre) => demander({ type: 'decrets-an', filtre }).then((m) => m.decrets),
  };
}
