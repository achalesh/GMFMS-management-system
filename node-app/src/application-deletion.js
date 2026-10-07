import {FormError} from './registration-fields.js';
import {policyLock,getApplication} from './registration-services.js';
import {loadUser} from './policies.js';
import {auditChange} from './administration.js';
export const deletionReasons=['Rejected application entered in error','Applicant requested deletion','Duplicate record cleanup'];
export async function deleteRejectedApplication(db,actorId,id,input){return db.transaction(async tx=>{
 await policyLock(tx);
 const a=await getApplication(tx,id,await loadUser(tx,actorId),'applications.delete');
 if(a.status!=='REJECTED'||(await tx.all('SELECT id FROM gmf_facilitators WHERE application_id=?',[id])).length)throw new FormError('Only rejected applications without a facilitator record can be permanently deleted.',409);
 if(a.revision!==Number(input.revision))throw new FormError('Application changed. Reload before deleting.',409);
 if(input.confirmed!=='on'||input.reference!==a.number)throw new FormError('Confirm deletion and enter the exact application reference.');
 if(!deletionReasons.includes(input.reason))throw new FormError('Choose a deletion reason.');
 await tx.run('DELETE FROM gmf_corrections WHERE application_id=?',[id]);
 await tx.run('DELETE FROM gmf_review_events WHERE application_id=?',[id]);
 await tx.run('DELETE FROM gmf_uploads WHERE owner_id=?',[id]);
 await tx.run('DELETE FROM gmf_drafts WHERE id=?',[id]);
 await tx.run('DELETE FROM gmf_applications WHERE id=?',[id]);
 await auditChange(tx,actorId,'application.deleted',id,input.reason,{reference:a.number,previous_status:'REJECTED'});
});}
