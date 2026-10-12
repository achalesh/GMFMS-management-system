import {readFileSync} from 'node:fs';
import {fields} from './registration-fields.js';
const translations=JSON.parse(readFileSync(new URL('../data/registration-ml.json',import.meta.url),'utf8'));
const labels=Object.fromEntries(Object.values(fields).flat().map(field=>[field.name.replaceAll('_',' '),field.label]));
export const bilingual=value=>{const label=labels[value]||value;return translations[label]?label+' / '+translations[label]:label;};
