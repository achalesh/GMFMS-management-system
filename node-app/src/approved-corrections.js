import {randomUUID,randomBytes} from 'node:crypto';
import {FormError} from './registration-fields.js';
import {loadUser,can} from './policies.js';
import {policyLock,getApplication,validateApplication} from './registration-services.js';
import {facilitator} from './registry.js';
import {uniqueContacts} from './member-rules.js';
import {refreshCorrectedCard,authorization} from './cards.js';
import {digest,correctionChoices} from './corrections.js';
async function log(tx,a,user,action,reason){await tx.run('INSERT INTO gmf_review_events(id,application_id,actor_id,action,from_status,to_status,reason,created_at) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),a.id,user,action,'APPROVED','APPROVED',reason,Date.now()]);await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),user,'application.'+action,Date.now()]);}
export async function requestApprovedCorrection(tx,user,a,input){
 const row=(await tx.all('SELECT id FROM gmf_facilitators WHERE application_id=?',[a.id]))[0];if(!row)throw new FormError('Approved facilitator unavailable.',404);
 const f=await facilitator(tx,row.id,user,'applications.review');if(await authorization(tx,f)!=='ACTIVE')throw new FormError('Only an active approved facilitator can use this correction workflow.');
 const previous=(await tx.all("SELECT * FROM gmf_approved_corrections WHERE application_id=? AND state IN ('OPEN','SUBMITTED') ORDER BY created_at DESC",[a.id]))[0];
 if(input.action==='request_correction'&&previous)throw new FormError('An approved-record correction is already pending.',409);
 if(input.action!=='request_correction'&&!previous)throw new FormError('No pending correction exists.',409);
 if(input.action==='renew_correction'&&previous.state!=='OPEN')throw new FormError('Review submitted changes before requesting another correction.',409);
 let allowed=typeof input.allowed_fields==='string'?[input.allowed_fields]:input.allowed_fields;
 if(input.action==='renew_correction')allowed=JSON.parse((await tx.all('SELECT fields FROM gmf_corrections WHERE id=?',[previous.id]))[0].fields);
 if(input.action!=='cancel_correction'&&(!Array.isArray(allowed)||!allowed.length||allowed.some(key=>!correctionChoices.some(([name])=>key===name))))throw new FormError('Select valid fields for correction.');
 if(previous){await tx.run("UPDATE gmf_approved_corrections SET state='CANCELLED' WHERE id=?",[previous.id]);await tx.run('DELETE FROM gmf_uploads WHERE owner_id=?',[previous.id]);}
 await tx.run('UPDATE gmf_corrections SET used=1 WHERE application_id=?',[a.id]);
 await tx.run('UPDATE gmf_applications SET revision=revision+1 WHERE id=?',[a.id]);let token;
 if(input.action!=='cancel_correction'){
 const id=randomUUID();token=randomBytes(32).toString('hex');await tx.run('INSERT INTO gmf_corrections(id,application_id,digest,fields,message,expires_at) VALUES (?,?,?,?,?,?)',[id,a.id,digest(token),JSON.stringify([...new Set(allowed)]),input.reason.trim(),Date.now()+48*3600000]);
 await tx.run('INSERT INTO gmf_approved_corrections(id,application_id,app_revision,facilitator_revision,original_payload,payload,changed,created_at) VALUES (?,?,?,?,?,?,?,?)',[id,a.id,a.revision+1,f.revision,a.payload,a.payload,'[]',Date.now()]);
 }
 await log(tx,a,user.id,input.action,input.reason.trim());return token;
}
export async function decideApprovedCorrection(db,cfg,userId,applicationId,input){return db.transaction(async tx=>{
 await policyLock(tx);const user=await loadUser(tx,userId),a=await getApplication(tx,applicationId,user,'applications.approve');
 const change=(await tx.all("SELECT * FROM gmf_approved_corrections WHERE id=? AND application_id=? AND state='SUBMITTED'",[input.correction_id||'',a.id]))[0];
 if(!change||a.status!=='APPROVED'||a.revision!==Number(input.revision)||a.revision!==change.app_revision)throw new FormError('This application changed. Reload and request a fresh correction.',409);
 const reason=typeof input.reason==='string'?input.reason.trim():'';if(!reason||reason.length>2000)throw new FormError('Provide a decision reason within 2,000 characters.');
 if(!['approve','reject'].includes(input.action))throw new FormError('Choose approve or reject.');
 if(input.action==='approve'){
 if(input.verified!=='on')throw new FormError('Confirm the corrected information has been verified.');
 const frow=(await tx.all('SELECT id FROM gmf_facilitators WHERE application_id=?',[a.id]))[0],f=await facilitator(tx,frow.id,user,'facilitators.change');
 if(!can(user,'cards.issue',f)||f.revision!==change.facilitator_revision)throw new FormError('Facilitator changed or card access is unavailable. Request a fresh correction.',409);
 if(await authorization(tx,f)!=='ACTIVE')throw new FormError('The facilitator must still be active.');
 const data=JSON.parse(change.payload),personal=data[2];await validateApplication(tx,a.id,data);await uniqueContacts(tx,personal,a.id);
 for(const upload of await tx.all('SELECT slot,mime,body,sha256 FROM gmf_uploads WHERE owner_id=?',[change.id])){await tx.run('DELETE FROM gmf_uploads WHERE owner_id=? AND slot=?',[a.id,upload.slot]);await tx.run('INSERT INTO gmf_uploads(owner_id,slot,mime,body,sha256) VALUES (?,?,?,?,?)',[a.id,upload.slot,upload.mime,upload.body,upload.sha256]);}
 await tx.run('UPDATE gmf_applications SET payload=?,full_name=?,normalized_name=?,mobile=?,email=? WHERE id=?',[change.payload,personal.full_name,personal.full_name.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim(),personal.mobile,personal.email,a.id]);
 await tx.run('UPDATE gmf_facilitators SET full_name=? WHERE id=?',[personal.full_name,f.id]);
 await refreshCorrectedCard(tx,cfg,user,await facilitator(tx,f.id,user,'cards.issue'),reason);
 await tx.run("INSERT OR IGNORE INTO gmf_registry_meta(id,notes) VALUES (?,'')",[f.id]);await tx.run('UPDATE gmf_registry_meta SET revision=revision+1 WHERE id=?',[f.id]);
 }
 await tx.run('UPDATE gmf_approved_corrections SET state=? WHERE id=?',[input.action==='approve'?'APPROVED':'REJECTED',change.id]);await tx.run('DELETE FROM gmf_uploads WHERE owner_id=?',[change.id]);await tx.run('UPDATE gmf_applications SET revision=revision+1 WHERE id=?',[a.id]);await log(tx,a,userId,'approved_correction_'+input.action,reason);
});}
