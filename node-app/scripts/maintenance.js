import 'dotenv/config';
import {expireFacilitators} from '../src/registry.js';
import {config} from '../src/config.js';
import {database} from '../src/database.js';
import {policyLock} from '../src/registration-services.js';
const db=await database(config());
try{await expireFacilitators(db);await db.transaction(async tx=>{
 await policyLock(tx);const now=Date.now();
 const expired=await tx.all('SELECT id FROM gmf_drafts WHERE expires_at<? AND submitted=0',[now]);
 for(const row of expired){await tx.run('DELETE FROM gmf_uploads WHERE owner_id=?',[row.id]);await tx.run('DELETE FROM gmf_drafts WHERE id=? AND submitted=0',[row.id]);}
 await tx.run('DELETE FROM gmf_sessions WHERE expires_at<?',[now]);await tx.run('DELETE FROM gmf_budgets WHERE expires_at<?',[now]);
 console.log(`Removed ${expired.length} expired draft(s); expired sessions and throttle records cleaned.`);
 });}finally{await db.close();}
