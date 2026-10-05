import {randomUUID} from 'node:crypto';
import {FormError} from './registration-fields.js';
import {can,loadUser} from './policies.js';
import {policyLock,getApplication,reviewAction} from './registration-services.js';
export const today=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});
export const registrySelect=`SELECT f.*,COALESCE(m.revision,1) AS revision,COALESCE(m.ended,0) AS ended,COALESCE(m.reference,'') AS reference,COALESCE(m.notes,'') AS notes,b.code AS block_code,d.code AS district_code,p.name AS panchayat_name FROM gmf_facilitators f LEFT JOIN gmf_registry_meta m ON m.id=f.id JOIN gmf_panchayats p ON p.code=f.panchayat_code JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code`;
export const effectiveStatus=f=>f.status==='ACTIVE'&&f.valid_until<today()?'EXPIRED':f.status;
export async function facilitator(db,id,user,capability='facilitators.view'){const row=(await db.all(registrySelect+' WHERE f.id=?',[id]))[0];if(!row||!can(user,capability,row))throw new FormError('Facilitator unavailable.',404);return row;}
async function location(tx,code,user){const row=(await tx.all(`SELECT p.code,b.code AS block_code,d.code AS district_code FROM gmf_panchayats p JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code JOIN gmf_states s ON s.code=d.state_code WHERE p.code=? AND p.active=1 AND b.active=1 AND d.active=1 AND s.active=1`,[code]))[0];if(!row)throw new FormError('Select an active panchayat.');if(!can(user,'facilitators.change',row))throw new FormError('Target location is outside your jurisdiction.',403);return row;}
const snapshot=f=>Object.fromEntries(['status','valid_until','panchayat_code','role','revision','ended','reference','notes'].map(k=>[k,f[k]]));
async function history(tx,f,actor,action,reason,old){await tx.run('INSERT INTO gmf_registry_history(id,facilitator_id,actor_id,action,reason,snapshot,created_at) VALUES (?,?,?,?,?,?,?)',[randomUUID(),f.id,actor,action,reason,JSON.stringify({old,new:snapshot(f)}),Date.now()]);await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),actor,'facilitator.'+action,Date.now()]);}
export async function registryAction(db,userId,id,input){return db.transaction(async tx=>{
 await policyLock(tx);const user=await loadUser(tx,userId),f=await facilitator(tx,id,user,'facilitators.change'),old=snapshot(f),action=input.action,reason=typeof input.reason==='string'?input.reason.trim():'';
 if(f.revision!==Number(input.revision))throw new FormError('This facilitator changed. Reload before continuing.',409);
 if(!reason||reason.length>2000)throw new FormError('Provide a reason within 2,000 characters.');
 if(['REVOKED','REPLACED'].includes(f.status))throw new FormError('Revoked and replaced records are historical and cannot be edited.');
 if(['suspend','inactivate','resign','revoke'].includes(action)){
 const target={suspend:'SUSPENDED',inactivate:'INACTIVE',resign:'INACTIVE',revoke:'REVOKED'}[action];if(f.ended&&action!=='revoke'||f.status===target&&action!=='resign')throw new FormError('This status action is unavailable.');f.status=target;if(['resign','revoke'].includes(action))f.ended=1;
 }else if(action==='reactivate'){
 if(effectiveStatus(f)==='ACTIVE')throw new FormError('This facilitator is already active.');if(f.valid_until<today())throw new FormError('Renew expired validity before reactivation.');await location(tx,f.panchayat_code,user);f.status='ACTIVE';if(f.ended){f.reference='';f.notes='';}f.ended=0;
 }else if(action==='renew'){
 const value=input.valid_until,date=new Date(value);if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||Number.isNaN(+date)||date.toISOString().slice(0,10)!==value||value<=today()||value<=f.valid_until||(+date-Date.parse(today()))/86400000>3650)throw new FormError('New validity must extend the existing date and be within ten years.');f.valid_until=value;if(!f.ended&&['ACTIVE','EXPIRED'].includes(f.status)){await location(tx,f.panchayat_code,user);f.status='ACTIVE';}
 }else if(action==='transfer'||action==='role'){
 if(effectiveStatus(f)!=='ACTIVE'||f.ended)throw new FormError('Only active current appointments may transfer or change role.');
 const target=action==='transfer'?input.panchayat:f.panchayat_code;if(typeof target!=='string')throw new FormError('Choose a panchayat.');await location(tx,target,user);
 const role=action==='role'?input.role:f.role;if(!['PRIMARY','ASSISTANT','ADDITIONAL'].includes(role))throw new FormError('Choose a valid role.');if(target===f.panchayat_code&&role===f.role)throw new FormError('Choose a different panchayat or role.');f.panchayat_code=target;f.role=role;f.reference='';f.notes='';
 }else if(action==='details'){
 if(f.ended)throw new FormError('Historical appointment details cannot be edited.');for(const [key,max] of [['reference',150],['notes',2000]]){if(typeof input[key]!=='string'||input[key].length>max)throw new FormError('Check the appointment reference and notes.');f[key]=input[key].trim();}if(f.reference===old.reference&&f.notes===old.notes)throw new FormError('Change the reference or notes before saving.');
 }else if(action==='replace'){
 if(f.role!=='PRIMARY'||f.ended)throw new FormError('Replacement requires a current primary appointment.');
 const candidate=await getApplication(tx,input.replacement_id,user,'applications.approve');if(candidate.panchayat_code!==f.panchayat_code||candidate.status!=='UNDER_REVIEW')throw new FormError('Choose an application under review in the same panchayat.');
 f.status='REPLACED';f.ended=1;await tx.run("UPDATE gmf_facilitators SET status='REPLACED',primary_key=NULL WHERE id=?",[id]);
 await reviewAction({transaction:fn=>fn(tx)},userId,candidate.id,{action:'approve',revision:input.application_revision,role:'PRIMARY',verified:input.verified,acknowledge:input.acknowledge,reason});
 }else throw new FormError('Unknown registry action.');
 const primary=f.status==='ACTIVE'&&!f.ended&&f.valid_until>=today()&&f.role==='PRIMARY'?f.panchayat_code:null;
 if(primary){await tx.run('UPDATE gmf_facilitators SET primary_key=NULL WHERE primary_key=? AND valid_until<?',[primary,today()]);if((await tx.all('SELECT id FROM gmf_facilitators WHERE primary_key=? AND id<>?',[primary,id])).length)throw new FormError('This panchayat already has an active primary facilitator.',409);}
 f.revision++;await tx.run('UPDATE gmf_facilitators SET status=?,valid_until=?,panchayat_code=?,role=?,primary_key=? WHERE id=?',[f.status,f.valid_until,f.panchayat_code,f.role,primary,id]);
 await tx.run("INSERT OR IGNORE INTO gmf_registry_meta(id,notes) VALUES (?,'')",[id]);await tx.run('UPDATE gmf_registry_meta SET revision=?,ended=?,reference=?,notes=? WHERE id=?',[f.revision,f.ended,f.reference,f.notes,id]);await history(tx,f,userId,action,reason,old);
 });}
export async function expireFacilitators(db){return db.transaction(async tx=>{await policyLock(tx);const rows=await tx.all(registrySelect+" WHERE f.status='ACTIVE' AND f.valid_until<?",[today()]);for(const f of rows){const old=snapshot(f);f.status='EXPIRED';f.revision++;await tx.run("UPDATE gmf_facilitators SET status='EXPIRED',primary_key=NULL WHERE id=?",[f.id]);await tx.run("INSERT OR IGNORE INTO gmf_registry_meta(id,notes) VALUES (?,'')",[f.id]);await tx.run('UPDATE gmf_registry_meta SET revision=? WHERE id=?',[f.revision,f.id]);await history(tx,f,null,'expired','Authorization validity elapsed.',old);}return rows.length;});}
