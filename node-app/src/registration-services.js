import {uniqueContacts,panchayatCapacity} from './member-rules.js';
import {settings} from './settings.js';
import {randomUUID} from 'node:crypto';
import {FormError,validateStep,catalog,slots} from './registration-fields.js';
import {can,loadUser} from './policies.js';
export async function policyLock(tx){await tx.run('UPDATE gmf_registration_policy SET app_sequence=app_sequence WHERE id=1');return (await tx.all('SELECT * FROM gmf_registration_policy WHERE id=1'))[0];}
export async function newDraft(db){if(!(await settings(db,'system')).data.registration_open)throw new FormError('New registration is currently closed.',403);const id=randomUUID();await db.run('INSERT INTO gmf_drafts(id,payload,expires_at) VALUES (?,?,?)',[id,'{}',Date.now()+86400000]);return id;}
export async function getDraft(db,id){const d=(await db.all('SELECT * FROM gmf_drafts WHERE id=?',[id||'']))[0];if(!d||d.expires_at<Date.now())throw new FormError('Your draft expired. Start a new application.',410);return {...d,data:JSON.parse(d.payload)};}
function editable(d,revision){if(d.submitted)throw new FormError('This application has already been submitted.',409);if(d.revision!==Number(revision))throw new FormError('This form changed in another tab. Reload before continuing.',409);}
export async function saveStep(db,id,step,revision,input,uploads={}){
 return db.transaction(async tx=>{await policyLock(tx);const d=await getDraft(tx,id);editable(d,revision);if(!Number.isInteger(step)||step<1||step>5||step>d.completed+1)throw new FormError('Complete the previous steps first.');
 if(step<5){d.data[step]=await validateStep(tx,step,input);if(step===2)await uniqueContacts(tx,d.data[step]);}
 else{
 for(const slot of slots){if(slot!=='photo'&&input['remove_'+slot]==='on')await tx.run('DELETE FROM gmf_uploads WHERE owner_id=? AND slot=?',[id,slot]);if(uploads[slot]){const u=uploads[slot];await tx.run('DELETE FROM gmf_uploads WHERE owner_id=? AND slot=?',[id,slot]);await tx.run('INSERT INTO gmf_uploads(owner_id,slot,mime,body,sha256) VALUES (?,?,?,?,?)',[id,slot,u.mime,u.body,u.sha256]);}}
 if(!(await tx.all("SELECT slot FROM gmf_uploads WHERE owner_id=? AND slot='photo'",[id])).length)throw new FormError('Upload a profile photograph.');
 const required=(await settings(tx,'system')).data.required_documents;for(const code of required)if(!(await tx.all('SELECT slot FROM gmf_uploads WHERE owner_id=? AND slot=?',[id,'doc_'+code])).length)throw new FormError('Upload required document: '+code+'.');
 }
 await tx.run('UPDATE gmf_drafts SET payload=?,completed=?,revision=revision+1 WHERE id=?',[JSON.stringify(d.data),Math.max(d.completed,step),id]);
 });
}
export async function validateApplication(db,id,data){for(let step=1;step<=4;step++)await validateStep(db,step,data[step]||{});if(!(await db.all("SELECT slot FROM gmf_uploads WHERE owner_id=? AND slot='photo'",[id])).length)throw new FormError('A profile photograph is required.');for(const code of (await settings(db,'system')).data.required_documents)if(!(await db.all('SELECT slot FROM gmf_uploads WHERE owner_id=? AND slot=?',[id,'doc_'+code])).length)throw new FormError('Required document missing: '+code+'.');}
export async function submit(db,id,revision,input){return db.transaction(async tx=>{
 const policy=await policyLock(tx),d=await getDraft(tx,id);if(d.submitted)return (await tx.all('SELECT number FROM gmf_applications WHERE id=?',[id]))[0].number;editable(d,revision);
 if(d.completed<5)throw new FormError('Complete all information steps first.');
 if(input.accuracy!=='on'||input.processing!=='on'||input.website||input.consent_version!==policy.consent_version)throw new FormError('Accept the current required declarations and consent.');
 await validateApplication(tx,id,d.data);await uniqueContacts(tx,d.data[2],id);
 d.data.consent={version:policy.consent_version,at:Date.now(),text:catalog.CONSENT,accuracy:true,processing:true,public_mobile:input.public_mobile==='on',public_email:input.public_email==='on',public_social:input.public_social==='on'};
 const number=`GS-APP-${new Date().getUTCFullYear()}-${String(policy.app_sequence+1).padStart(6,'0')}`,personal=d.data[2];
 await tx.run('UPDATE gmf_registration_policy SET app_sequence=app_sequence+1 WHERE id=1');
 await tx.run('INSERT INTO gmf_applications(id,number,panchayat_code,payload,full_name,normalized_name,mobile,email,submitted_at) VALUES (?,?,?,?,?,?,?,?,?)',[id,number,d.data[1].panchayat,JSON.stringify(d.data),personal.full_name,personal.full_name.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim(),personal.mobile,personal.email,Date.now()]);
 await tx.run('UPDATE gmf_drafts SET submitted=1,revision=revision+1 WHERE id=?',[id]);
 await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,NULL,?,?)',[randomUUID(),'application.submitted',Date.now()]);return number;
 });}
export const applicationSelect=`SELECT a.*,b.code AS block_code,d.code AS district_code,p.name AS panchayat_name FROM gmf_applications a JOIN gmf_panchayats p ON p.code=a.panchayat_code JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code`;
export async function getApplication(db,id,user,capability='applications.view'){
 const a=(await db.all(applicationSelect+' WHERE a.id=?',[id]))[0];if(!a||!can(user,capability,a))throw new FormError('Application unavailable.',404);return {...a,data:JSON.parse(a.payload)};
}
export async function duplicates(db,a){return db.all(`SELECT number FROM gmf_applications WHERE id<>? AND (mobile=? OR (email<>'' AND email=?) OR (normalized_name=? AND panchayat_code=?))`,[a.id,a.mobile,a.email,a.normalized_name,a.panchayat_code]);}
export async function reviewAction(db,userId,id,input){return db.transaction(async tx=>{
 const policy=await policyLock(tx),user=await loadUser(tx,userId);
 const transitions={start_review:['SUBMITTED','UNDER_REVIEW','applications.review'],approve:['UNDER_REVIEW','APPROVED','applications.approve'],reject:['UNDER_REVIEW','REJECTED','applications.approve']};
 const transition=transitions[input.action];if(!transition)throw new FormError('Unknown review action.');
 const a=await getApplication(tx,id,user,transition[2]);
 if(a.revision!==Number(input.revision)||a.status!==transition[0])throw new FormError('This application changed. Reload before taking action.',409);
 const reason=typeof input.reason==='string'?input.reason.trim():'';if(reason.length>2000||input.action==='reject'&&!reason)throw new FormError('Provide a reason of up to 2,000 characters.');
 if(input.action==='approve'){
 if(input.verified!=='on')throw new FormError('Confirm that the application, documents and consent were verified.');
 await validateApplication(tx,id,a.data);await uniqueContacts(tx,a.data[2],id);await panchayatCapacity(tx,a.panchayat_code);if(!a.data.consent?.accuracy||!a.data.consent?.processing||!a.data.consent?.at)throw new FormError('Recorded consent is incomplete.');
 if((await duplicates(tx,a)).length&&(input.acknowledge!=='on'||!reason))throw new FormError('Acknowledge the duplicate warnings and explain your decision.');
 const role=input.role;if(!['PRIMARY','ASSISTANT','ADDITIONAL'].includes(role))throw new FormError('Choose a valid appointment role.');
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});
 await tx.run('UPDATE gmf_facilitators SET primary_key=NULL WHERE primary_key=? AND valid_until<?',[a.panchayat_code,today]);
 if(role==='PRIMARY'&&(await tx.all('SELECT id FROM gmf_facilitators WHERE primary_key=?',[a.panchayat_code])).length)throw new FormError('This panchayat already has a primary facilitator. Use a replacement workflow.',409);
 await tx.run('INSERT OR IGNORE INTO gmf_facilitator_sequences(district_code) VALUES (?)',[a.district_code]);await tx.run('UPDATE gmf_facilitator_sequences SET value=value+1 WHERE district_code=?',[a.district_code]);const seq=(await tx.all('SELECT value FROM gmf_facilitator_sequences WHERE district_code=?',[a.district_code]))[0].value;
 const number=`${policy.prefix}-${a.district_code}-${String(seq).padStart(4,'0')}`,expiry=new Date(today+'T00:00:00Z');expiry.setUTCDate(expiry.getUTCDate()+policy.validity_days);
 await tx.run('INSERT INTO gmf_facilitators(id,application_id,number,panchayat_code,full_name,role,valid_until,primary_key,approved_by,approved_at) VALUES (?,?,?,?,?,?,?,?,?,?)',[randomUUID(),id,number,a.panchayat_code,a.full_name,role,expiry.toISOString().slice(0,10),role==='PRIMARY'?a.panchayat_code:null,user.id,Date.now()]);
 }
 await tx.run('UPDATE gmf_applications SET status=?,revision=revision+1 WHERE id=?',[transition[1],id]);
 await tx.run('INSERT INTO gmf_review_events(id,application_id,actor_id,action,from_status,to_status,reason,created_at) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),id,user.id,input.action,a.status,transition[1],reason,Date.now()]);
 await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),user.id,'application.'+input.action,Date.now()]);
 });}
