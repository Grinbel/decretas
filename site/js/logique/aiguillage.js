/**
 * « Quel acte chercher ? » — walking the decision tree of site/contenu/aiguillage.json.
 * Pure functions, no DOM; tested in tests/js/ui-aiguillage.test.mjs.
 *
 * The state of the flow is the list of the answers given, kept in the address
 * (#/quel-acte?r=d-ancetre,f-musulmane), so that "back" is the browser's back, a trail can be
 * shown, and an outcome can be bookmarked or sent. An outcome can also be named directly
 * (#/quel-acte/<issue id>).
 */

/**
 * Follow the answers from the first question.
 * @param {Object} arbre parsed aiguillage.json
 * @param {string[]} reponses answer ids, in order
 * @returns {{
 *   chemin: Array<{question: Object, reponse: Object}>,   the answers that could be followed
 *   question: Object|null,   the question to ask now (null when an outcome is reached)
 *   issue: Object|null,      the outcome reached
 *   ignorees: string[] }}    answer ids that did not fit the tree (stale or mistyped address)
 */
export function parcourir(arbre, reponses = []) {
  const questions = new Map((arbre?.questions ?? []).map((q) => [q.id, q]));
  const issues = new Map((arbre?.issues ?? []).map((i) => [i.id, i]));
  const chemin = [];
  let question = questions.get(arbre?.depart) ?? null;
  let issue = null;
  const ids = reponses.filter((x) => typeof x === 'string' && x !== '');
  let i = 0;
  for (; i < ids.length && question !== null; i++) {
    const reponse = (question.reponses ?? []).find((r) => r.id === ids[i]);
    if (reponse === undefined) break;
    chemin.push({ question, reponse });
    const vers = reponse.vers ?? {};
    if (vers.type === 'issue') {
      issue = issues.get(vers.id) ?? null;
      question = null;
      i++;
      break;
    }
    question = questions.get(vers.id) ?? null;
  }
  return { chemin, question, issue, ignorees: ids.slice(chemin.length) };
}

/** The outcome named directly by its id, or null. */
export function issueParId(arbre, id) {
  return (arbre?.issues ?? []).find((x) => x.id === id) ?? null;
}

/** "d-ancetre,f-musulmane" -> ['d-ancetre', 'f-musulmane']; only plausible ids are kept. */
export function lireReponses(texte) {
  return String(texte ?? '').split(',').map((s) => s.trim()).filter((s) => /^[a-z0-9-]{1,60}$/.test(s)).slice(0, 12);
}

/** Every outcome reachable from the first question (to test that each one can be drawn). */
export function issuesAtteignables(arbre) {
  const questions = new Map((arbre?.questions ?? []).map((q) => [q.id, q]));
  const vues = new Set();
  const out = new Set();
  const todo = [arbre?.depart];
  while (todo.length > 0) {
    const id = todo.pop();
    if (vues.has(id) || !questions.has(id)) continue;
    vues.add(id);
    for (const r of questions.get(id).reponses ?? []) {
      if (r.vers?.type === 'issue') out.add(r.vers.id);
      else todo.push(r.vers?.id);
    }
  }
  return [...out];
}

/** The shortest list of answers that leads to an outcome (for a link that rebuilds the trail). */
export function cheminVers(arbre, idIssue) {
  const questions = new Map((arbre?.questions ?? []).map((q) => [q.id, q]));
  const file = [[arbre?.depart, []]];
  const vues = new Set();
  while (file.length > 0) {
    const [id, chemin] = file.shift();
    if (vues.has(id) || !questions.has(id)) continue;
    vues.add(id);
    for (const r of questions.get(id).reponses ?? []) {
      if (r.vers?.type === 'issue' && r.vers.id === idIssue) return [...chemin, r.id];
      if (r.vers?.type === 'question') file.push([r.vers.id, [...chemin, r.id]]);
    }
  }
  return null;
}

/**
 * The periods of the tree that matter for someone born about "naissance": those that end on or
 * after the year of the legal minimum age. Without a year, all of them.
 */
export function epoquesPour(arbre, naissance) {
  const epoques = arbre?.epoques ?? [];
  const age = arbre?.age_minimal?.decret;
  if (!Number.isInteger(naissance) || !Number.isInteger(age)) return epoques;
  return epoques.filter((e) => !Number.isInteger(e.annees?.fin) || e.annees.fin >= naissance + age);
}
