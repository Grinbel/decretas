/**
 * The strings of the interface. Every sentence the page shows that does not come from a
 * content file (site/contenu/*.json) or from a data file lives in ONE module per language:
 * textes/fr.js today. To add a language: write textes/<code>.js with the same keys, register
 * it below, and set "direction" ('rtl' for Arabic). The CSS uses logical properties only, so
 * a right-to-left language needs no second stylesheet.
 */

import { fr } from './fr.js';
import { typographierTout } from './typographie.js';

const LANGUES = { fr: { textes: fr, direction: 'ltr' } };

/** Code of the language in use. */
export const langue = 'fr';
/** Writing direction of the language in use. */
export const direction = LANGUES[langue].direction;
/** The strings of the language in use (with French no-break spaces: see typographie.js). */
export const T = typographierTout(LANGUES[langue].textes);
