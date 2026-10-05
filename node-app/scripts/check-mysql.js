import 'dotenv/config';
import {randomUUID} from 'node:crypto';
import {config} from '../src/config.js';
import {database} from '../src/database.js';
import {schemaVersion} from '../src/schema.js';

const cfg=config();
if(!cfg.mysql){console.error('MySQL check requires MYSQL_URL in a private environment file or hosting environment.');process.exit(1);}
let db;
try{
 db=await database(cfg);
 const [variables]=await db.all('SELECT @@character_set_connection AS charset, @@max_allowed_packet AS packet');
 const [schema]=await db.all('SELECT MAX(version) AS version FROM gmf_schema');
 if(variables.charset!=='utf8mb4'||Number(variables.packet)<8*1024*1024||schema.version!==schemaVersion)throw Error('requirements');
 const engines=await db.all("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'gmf\\_%'");
 if(!engines.length||engines.some(t=>t.ENGINE!=='InnoDB'))throw Error('transactional tables required');
 const id=randomUUID(),text='സ്വാശ്രയ ഗ്രാമങ്ങൾ • MySQL staging check';
 const rollback=Symbol('expected rollback');
 try{await db.transaction(async tx=>{
  await tx.run('INSERT INTO gmf_audit(id,action,created_at) VALUES (?,?,?)',[id,'staging.mysql_check',Date.now()]);
  await tx.run('INSERT INTO gmf_audit_details(id,entity,reason,changes) VALUES (?,?,?,?)',[id,'staging',text,'{}']);
  const [row]=await tx.all('SELECT reason FROM gmf_audit_details WHERE id=?',[id]);if(row?.reason!==text)throw Error('unicode');
  throw rollback;
 });}catch(e){if(e!==rollback)throw e;}
 if((await db.all('SELECT id FROM gmf_audit WHERE id=?',[id])).length)throw Error('rollback');
 console.log('MySQL check passed: current schema, utf8mb4, upload packet capacity, Malayalam round trip and transaction rollback. No test records retained.');
}catch{console.error('MySQL check failed. Verify network access, credentials, schema migration, utf8mb4 and max_allowed_packet >= 8 MB. No credentials are printed.');process.exitCode=1;}
finally{await db?.close();}
