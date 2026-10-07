import {randomUUID} from 'node:crypto';
import {FormError} from './registration-fields.js';
import {policyLock} from './registration-services.js';
export const withdrawable=['SUBMITTED','UNDER_REVIEW','CORRECTION_REQUIRED'];
export async function cancelRegistration(db,ownedId,kind,input){
 if(input.confirmed!=='on')throw new FormError('Confirm before continuing.');
 return db.transaction(async tx=>{
  await policyLock(tx);
  if(kind==='discard'){
   const d=(await tx.all('SELECT revision,submitted FROM gmf_drafts WHERE id=?',[ownedId||'']))[0];
   if(!d)throw new FormError('Draft unavailable in this browser session.',404);
   if(d.submitted||(await tx.all('SELECT id FROM gmf_applications WHERE id=?',[ownedId])).length)throw new FormError('Submitted applications cannot be discarded.',409);
   if(d.revision!==Number(input.revision))throw new FormError('Draft changed. Reload before discarding.',409);
   await tx.run('DELETE FROM gmf_uploads WHERE owner_id=?',[ownedId]);
   await tx.run('DELETE FROM gmf_drafts WHERE id=?',[ownedId]);
   await tx.run('INSERT INTO gmf_audit(id,action,created_at) VALUES (?,?,?)',[randomUUID(),'registration.draft_discarded',Date.now()]);
  }else if(kind==='withdraw'){
   const a=(await tx.all('SELECT status,revision FROM gmf_applications WHERE id=?',[ownedId||'']))[0];
   if(!a)throw new FormError('Application unavailable in this browser session.',404);
   if(!withdrawable.includes(a.status))throw new FormError('Only applications awaiting a decision can be withdrawn.',409);
   if(a.revision!==Number(input.revision))throw new FormError('Application changed. Reload before withdrawing.',409);
   const reason=typeof input.reason==='string'?input.reason.trim():'';
   if(!reason||reason.length>2000)throw new FormError('Provide a withdrawal reason within 2,000 characters.');
   await tx.run("UPDATE gmf_applications SET status='WITHDRAWN',revision=revision+1 WHERE id=?",[ownedId]);
   await tx.run('UPDATE gmf_corrections SET used=1 WHERE application_id=?',[ownedId]);
   await tx.run('INSERT INTO gmf_review_events(id,application_id,actor_id,action,from_status,to_status,reason,created_at) VALUES (?,?,?,?,?,?,?,?)',[randomUUID(),ownedId,'APPLICANT','withdraw',a.status,'WITHDRAWN',reason,Date.now()]);
   await tx.run('INSERT INTO gmf_audit(id,action,created_at) VALUES (?,?,?)',[randomUUID(),'application.withdrawn',Date.now()]);
  }else throw new FormError('Unknown cancellation action.');
 });
}
