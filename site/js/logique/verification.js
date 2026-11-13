/**
 * The honesty note of a block of the content files. Every statement there carries
 * "verification": {etat: 'verifie' | 'partiel' | 'non-verifie', note}. A statement that is not
 * « verifie » is never shown as established: its note goes with it (« À confirmer : … »), or a
 * generic sentence when the file gives none. Pure function; tested in ui-verification.test.mjs.
 */

import { T } from '../textes/index.js';

/**
 * @param {{etat?: string, note?: string}|null|undefined} verification
 * @returns {string|null} the sentence to show, or null for a verified statement
 */
export function noteDeVerification(verification) {
  const etat = verification?.etat;
  if (etat === undefined || etat === 'verifie') return null;
  const note = typeof verification.note === 'string' ? verification.note.trim() : '';
  if (note !== '') return note;
  return etat === 'partiel' ? T.verification.partiel : T.verification.nonVerifie;
}
