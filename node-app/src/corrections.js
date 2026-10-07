import {uniqueContacts} from './member-rules.js';
import {randomUUID,randomBytes,createHash} from 'node:crypto';
import {fields,slots,catalog,FormError,validateStep} from './registration-fields.js';
import {policyLock,getApplication,validateApplication} from './registration-services.js';
import {loadUser} from './policies.js';
export const correctionChoices=[...Object.values(fields).flat().map(f=>[f.name,f.label]),['photo','Profile photograph'],...catalog.DOCUMENTS.map(([k,v])=>['doc_'+k,v])];
export const digest=raw=>createHash('sha256').update(raw).digest('hex');
async function event(tx,a,actor,action,target,reason){await tx.run('INSERT INTO gmf_review_events(id,application_id,actor_id,action,from_status,to_status,reason,created_at) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),a.id,actor||'APPLICANT',action,a.status,target,reason,Date.now()]);await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),actor,'application.'+action,Date.now()]);}
export async function requestCorrection(db,userId,id,input){return db.transaction(async tx=>{
 await policyLock(tx);const a=await getApplication(tx,id,await loadUser(tx,userId),'applications.review');
 if(a.revision!==Number(input.revision))throw new FormError('This application changed. Reload before continuing.',409);
 const action=input.action,reason=typeof input.reason==='string'?input.reason.trim():'';
 if(!reason||reason.length>2000)throw new FormError('Provide correction instructions or a reason within 2,000 characters.');
 if(!['request_correction','renew_correction','cancel_correction'].includes(action)||a.status!==(action==='request_correction'?'UNDER_REVIEW':'CORRECTION_REQUIRED'))throw new FormError('This correction action is unavailable.',409);
 let allowed=typeof input.allowed_fields==='string'?[input.allowed_fields]:input.allowed_fields;
 if(action==='renew_correction'){const old=(await tx.all('SELECT fields FROM gmf_corrections WHERE application_id=? ORDER BY expires_at DESC',[id]))[0];if(!old)throw new FormError('No correction request exists.');allowed=JSON.parse(old.fields);}
 await tx.run('UPDATE gmf_corrections SET used=1 WHERE application_id=?',[id]);let token;
 if(action!=='cancel_correction'){
 if(!Array.isArray(allowed)||!allowed.length||allowed.some(f=>!correctionChoices.some(([key])=>key===f)))throw new FormError('Select valid fields for correction.');
 token=randomBytes(32).toString('hex');await tx.run('INSERT INTO gmf_corrections(id,application_id,digest,fields,message,expires_at) VALUES (?,?,?,?,?,?)',[randomUUID(),id,digest(token),JSON.stringify([...new Set(allowed)]),reason,Date.now()+48*3600000]);
 }
 const target=action==='cancel_correction'?'UNDER_REVIEW':'CORRECTION_REQUIRED';await tx.run('UPDATE gmf_applications SET status=?,revision=revision+1 WHERE id=?',[target,id]);await event(tx,a,userId,action,target,reason);return token;
 });}
export async function correctionTicket(db,hash){
 if(typeof hash!=='string'||!/^[a-f0-9]{64}$/.test(hash))throw new FormError('Correction link unavailable or expired.',410);
 const row=(await db.all(`SELECT c.*,a.payload,a.revision,a.status FROM gmf_corrections c JOIN gmf_applications a ON a.id=c.application_id WHERE c.digest=? AND c.used=0 AND c.expires_at>? AND a.status='CORRECTION_REQUIRED'`,[hash,Date.now()]))[0];if(!row)throw new FormError('Correction link unavailable or expired.',410);
 return {...row,allowed:JSON.parse(row.fields),data:JSON.parse(row.payload)};
}
export async function applyCorrection(db,hash,input,uploads={}){return db.transaction(async tx=>{
 const policy=await policyLock(tx),ticket=await correctionTicket(tx,hash),data=ticket.data;
 if(Number(input.revision)!==ticket.revision)throw new FormError('The application changed. Reload this form.',409);
 if(input.accuracy!=='on'||input.processing!=='on'||input.consent_version!==policy.consent_version)throw new FormError('Accept the current declaration and processing consent.');
 const changed=[];
 for(const [step,specs] of Object.entries(fields)){
 const merged={...data[step]};for(const f of specs)if(ticket.allowed.includes(f.name))merged[f.name]=input[f.name]??(f.multiple?[]:'');
 const cleaned=await validateStep(tx,Number(step),merged);
 for(const f of specs)if(ticket.allowed.includes(f.name)&&JSON.stringify(cleaned[f.name])!==JSON.stringify(data[step][f.name])){data[step][f.name]=cleaned[f.name];changed.push(f.name);}
 }
 for(const [slot,u] of Object.entries(uploads)){
 if(!ticket.allowed.includes(slot)||!slots.includes(slot))throw new FormError('This file was not requested.');
 const old=(await tx.all('SELECT sha256 FROM gmf_uploads WHERE owner_id=? AND slot=?',[ticket.application_id,slot]))[0];if(old?.sha256===u.sha256)continue;
 await tx.run('DELETE FROM gmf_uploads WHERE owner_id=? AND slot=?',[ticket.application_id,slot]);await tx.run('INSERT INTO gmf_uploads(owner_id,slot,mime,body,sha256) VALUES (?,?,?,?,?)',[ticket.application_id,slot,u.mime,u.body,u.sha256]);changed.push(slot);
 }
 if(!changed.length)throw new FormError('Make at least one requested correction before resubmitting.');
 await validateApplication(tx,ticket.application_id,data);await uniqueContacts(tx,data[2],ticket.application_id);
 data.consent={...data.consent,version:policy.consent_version,at:Date.now(),text:catalog.CONSENT,accuracy:true,processing:true};const personal=data[2];
 await tx.run("UPDATE gmf_applications SET payload=?,full_name=?,normalized_name=?,mobile=?,email=?,status='SUBMITTED',revision=revision+1 WHERE id=?",[JSON.stringify(data),personal.full_name,personal.full_name.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim(),personal.mobile,personal.email,ticket.application_id]);
 await tx.run('UPDATE gmf_corrections SET used=1 WHERE id=?',[ticket.id]);await event(tx,{id:ticket.application_id,status:ticket.status},null,'correction_resubmitted','SUBMITTED','Corrected fields: '+changed.join(', '));
 });}
