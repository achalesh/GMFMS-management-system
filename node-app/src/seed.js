import {readFile} from 'node:fs/promises';
export async function seed(db){
 const rows=JSON.parse(await readFile(new URL('../data/locations.json',import.meta.url),'utf8'));
 await db.transaction(async tx=>{for(const r of rows){
 await tx.run('INSERT OR IGNORE INTO gmf_states(code,name) VALUES (?,?)',[r.state_code,r.state_name_en]);
 await tx.run('INSERT OR IGNORE INTO gmf_districts(code,state_code,name,name_ml) VALUES (?,?,?,?)',[r.district_code,r.state_code,r.district_name_en,r.district_name_ml]);
 await tx.run('INSERT OR IGNORE INTO gmf_blocks(code,district_code,name,name_ml) VALUES (?,?,?,?)',[r.block_code,r.district_code,r.block_name_en,r.block_name_ml]);
 await tx.run('INSERT OR IGNORE INTO gmf_panchayats(code,block_code,name,name_ml) VALUES (?,?,?,?)',[r.sec_local_body_code,r.block_code,r.panchayat_name_en,r.panchayat_name_ml]);
 }});
}
