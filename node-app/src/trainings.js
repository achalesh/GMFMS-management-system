import {randomUUID} from 'node:crypto';
import {can,scopesFor,loadUser} from './policies.js';
import {FormError} from './registration-fields.js';
import {registrySelect,today} from './registry.js';
import {authorization} from './cards.js';
import {policyLock} from './registration-services.js';
import {auditChange} from './administration.js';
import {placesFor} from './reports.js';

export const attendanceLabels={PENDING:'Not marked / രേഖപ്പെടുത്തിയിട്ടില്ല',PRESENT:'Present / ഹാജർ',ABSENT:'Absent / ഹാജരായില്ല',LATE:'Late / വൈകിയെത്തി',EXCUSED:'Excused / അനുവദിച്ച ഒഴിവ്'};
export const trainingStatuses=['SCHEDULED','COMPLETED','CANCELLED'];
export const trainingCapability=(user,cap)=>!!user?.active&&!user.facilitator_id&&(!!user.superuser||scopesFor(user,cap).length>0);
export const inTrainingScope=(training,f)=>training.scope==='STATE'||training.district_code===f.district_code&&(training.scope==='DISTRICT'||training.block_code===f.block_code);
export function trainingVisible(user,training){return trainingCapability(user,'trainings.view')&&(training.scope==='STATE'||can(user,'trainings.view',training));}
const sqlTrainingJoin=db=>db.dialect==='mysql'?'CAST(t.id AS BINARY)=CAST(a.training_id AS BINARY)':'t.id=a.training_id';
export async function trainingRows(db){return db.all('SELECT * FROM gmf_trainings ORDER BY session_date DESC,starts_at DESC,title');}
export async function trainingRecord(db,user,id){const t=(await db.all('SELECT * FROM gmf_trainings WHERE id=?',[id]))[0];if(!t||!trainingVisible(user,t))throw new FormError('Training unavailable in your jurisdiction.',404);return t;}
export async function trainingRoster(db,user,t){
 const facilitators=(await db.all(registrySelect)).filter(f=>inTrainingScope(t,f)&&can(user,'trainings.view',f));const byId=new Map(facilitators.map(f=>[f.id,f]));
 return (await db.all('SELECT * FROM gmf_training_assignments WHERE training_id=? ORDER BY assigned_at,id',[t.id])).filter(a=>byId.has(a.facilitator_id)).map(a=>({...a,f:byId.get(a.facilitator_id),mayMark:can(user,'trainings.manage',byId.get(a.facilitator_id))}));
}
export async function assignableFacilitators(db,user,t){
 if(!trainingCapability(user,'trainings.manage'))return [];
 const existing=new Set((await db.all("SELECT facilitator_id FROM gmf_training_assignments WHERE training_id=? AND state='ASSIGNED'",[t.id])).map(a=>a.facilitator_id));
 const rows=(await db.all(registrySelect+" WHERE f.status='ACTIVE' AND f.valid_until>=? ORDER BY f.full_name",[today()])).filter(f=>!existing.has(f.id)&&!f.ended&&inTrainingScope(t,f)&&can(user,'trainings.manage',f));
 const eligible=[];for(const f of rows)if(await authorization(db,f)==='ACTIVE')eligible.push(f);return eligible;
}
function note(input){const value=typeof input.reason==='string'?input.reason.trim():'';if(!value||value.length>1000)throw new FormError('Provide a reason / verification note within 1,000 characters.');return value;}
function values(input){
 const output={};for(const [key,max] of [['title',180],['trainer',180],['venue',500],['description',2000]]){const value=input[key]??'';if(typeof value!=='string'||value.trim().length>max||['title','venue'].includes(key)&&!value.trim())throw new FormError('Check training title, trainer and venue / meeting details.');output[key]=value.trim();}
 const date=input.session_date,start=input.starts_at,end=input.ends_at;const validTime=value=>typeof value==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(value);
 if(typeof date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(date)||Number.isNaN(+new Date(date))||new Date(date).toISOString().slice(0,10)!==date||!validTime(start)||!validTime(end)||end<=start)throw new FormError('Choose a valid training date and start/end times on the same day (IST).');
 if(!['OFFLINE','ONLINE','HYBRID'].includes(input.mode))throw new FormError('Choose a valid training mode.');return {...output,session_date:date,starts_at:start,ends_at:end,mode:input.mode};
}
async function scopeFor(db,user,input){
 const scope=input.scope,district=input.district||null,block=input.block||null;if(!['STATE','DISTRICT','BLOCK'].includes(scope)||[district,block].some(value=>value!==null&&(typeof value!=='string'||value.length>30)))throw new FormError('Choose a valid training jurisdiction.');
 if(scope==='STATE'&&(district||block)||scope==='DISTRICT'&&(!district||block)||scope==='BLOCK'&&(!district||!block))throw new FormError('Choose locations matching the training scope.');
 const place={district_code:district,block_code:block};if(!can(user,'trainings.manage',place))throw new FormError('Cannot create training outside your management jurisdiction.',403);
 if(scope!=='STATE'){const places=await placesFor(db,user,'trainings.manage');if(!places.some(p=>p.district_code===district&&(!block||p.block_code===block)))throw new FormError('Choose an active district / block in your jurisdiction.');}
 return {scope,district_code:district,block_code:block};
}
function ids(value){const selected=typeof value==='string'?[value]:value;if(!Array.isArray(selected)||!selected.length||selected.length>50||selected.some(id=>typeof id!=='string'||id.length>36)||new Set(selected).size!==selected.length)throw new FormError('Select between 1 and 50 different facilitators / assignments.');return selected;}
export async function createTraining(db,userId,input){return db.transaction(async tx=>{
 await policyLock(tx);const user=await loadUser(tx,userId);if(!trainingCapability(user,'trainings.manage'))throw new FormError('Training management access denied.',403);
 const v=values(input),scope=await scopeFor(tx,user,input),id=randomUUID(),reason=note(input);
 await tx.run('INSERT INTO gmf_trainings(id,title,trainer,session_date,starts_at,ends_at,mode,venue,description,scope,district_code,block_code,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[id,v.title,v.trainer,v.session_date,v.starts_at,v.ends_at,v.mode,v.venue,v.description,scope.scope,scope.district_code,scope.block_code,userId,Date.now()]);
 await auditChange(tx,userId,'training.created',id,reason,{...v,...scope});return id;
});}
export async function trainingAction(db,userId,id,input){return db.transaction(async tx=>{
 await policyLock(tx);const user=await loadUser(tx,userId),t=await trainingRecord(tx,user,id);if(!trainingCapability(user,'trainings.manage'))throw new FormError('Training management access denied.',403);
 if(Number(input.training_revision)!==t.revision)throw new FormError('Training changed. Reload before saving.',409);const reason=note(input),action=input.action;
 if(action==='update'){
 if(!can(user,'trainings.manage',t))throw new FormError('Only the training jurisdiction manager can edit this session.',403);
 const v=values(input);if(!trainingStatuses.includes(input.status))throw new FormError('Choose a valid training status.');
 if((v.session_date!==t.session_date||v.starts_at!==t.starts_at||v.ends_at!==t.ends_at)&&(await tx.all("SELECT id FROM gmf_training_assignments WHERE training_id=? AND attendance<>'PENDING' LIMIT 1",[id])).length)throw new FormError('Attendance already exists. Create a separate session instead of changing its date or time.');
 if(input.status==='COMPLETED'&&v.session_date>today())throw new FormError('A future training cannot be marked completed.');
 await tx.run('UPDATE gmf_trainings SET title=?,trainer=?,session_date=?,starts_at=?,ends_at=?,mode=?,venue=?,description=?,status=?,revision=revision+1 WHERE id=?',[v.title,v.trainer,v.session_date,v.starts_at,v.ends_at,v.mode,v.venue,v.description,input.status,id]);
 await auditChange(tx,userId,'training.updated',id,reason,{before:t,after:{...v,status:input.status}});return;
 }
 if(t.status==='CANCELLED')throw new FormError('This training is cancelled.');
 if(action==='assign'){
 if(t.status!=='SCHEDULED')throw new FormError('Reopen the session before assigning additional facilitators.');
 for(const fId of ids(input.facilitator_ids)){
 const f=(await tx.all(registrySelect+' WHERE f.id=?',[fId]))[0];if(!f||!inTrainingScope(t,f)||!can(user,'trainings.manage',f))throw new FormError('A selected facilitator is outside your training jurisdiction.',403);
 if(await authorization(tx,f)!=='ACTIVE')throw new FormError('Assign only active approved facilitators.');
 const previous=(await tx.all('SELECT * FROM gmf_training_assignments WHERE training_id=? AND facilitator_id=?',[id,fId]))[0];if(previous?.state==='ASSIGNED')continue;
 if(previous)await tx.run("UPDATE gmf_training_assignments SET state='ASSIGNED',revision=revision+1,assigned_by=?,assigned_at=? WHERE id=?",[userId,Date.now(),previous.id]);
 else await tx.run('INSERT INTO gmf_training_assignments(id,training_id,facilitator_id,assigned_by,assigned_at) VALUES (?,?,?,?,?)',[randomUUID(),id,fId,userId,Date.now()]);
 await auditChange(tx,userId,'training.assigned',f.id,reason,{training_id:id,restored:!!previous});
 }
 await tx.run('UPDATE gmf_trainings SET revision=revision+1 WHERE id=?',[id]);return;
 }
 if(action!=='bulk_attendance'&&(typeof input.assignment_id!=='string'||input.assignment_id.length>36))throw new FormError('Select a valid assignment.');
 const selected=action==='bulk_attendance'?ids(input.assignment_ids):[input.assignment_id];
 if(!['attendance','bulk_attendance','cancel_assignment'].includes(action))throw new FormError('Unknown training action.');
 for(const assignmentId of selected){
 const a=(await tx.all('SELECT * FROM gmf_training_assignments WHERE id=? AND training_id=?',[assignmentId||'',id]))[0];if(!a||a.state!=='ASSIGNED')throw new FormError('Active assignment unavailable.',404);
 const f=(await tx.all(registrySelect+' WHERE f.id=?',[a.facilitator_id]))[0];if(!f||!inTrainingScope(t,f)||!can(user,'trainings.manage',f))throw new FormError('Attendance access denied for this facilitator.',403);
 if(action!=='bulk_attendance'&&Number(input.revision)!==a.revision)throw new FormError('Attendance changed. Reload before saving.',409);
 if(action==='cancel_assignment'){
 if(a.attendance!=='PENDING')throw new FormError('Attendance already exists. Correct attendance instead of cancelling the assignment.');
 await tx.run("UPDATE gmf_training_assignments SET state='CANCELLED',revision=revision+1 WHERE id=?",[a.id]);await auditChange(tx,userId,'training.assignment_cancelled',a.id,reason,{training_id:id});continue;
 }
 if(t.session_date>today())throw new FormError('Attendance cannot be marked before the training date.');
 if(!Object.hasOwn(attendanceLabels,input.attendance))throw new FormError('Choose a valid attendance status.');
 if(action==='bulk_attendance'&&(a.attendance!=='PENDING'||input.attendance==='PENDING'))throw new FormError('Bulk marking is only for unmarked assignments. Use the individual row to correct recorded attendance.',409);
 const arrival=typeof input.arrival_time==='string'?input.arrival_time:'';if(arrival&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(arrival)||arrival&&!['PRESENT','LATE'].includes(input.attendance))throw new FormError('Arrival time applies only to present / late attendance.');
 await tx.run('UPDATE gmf_training_assignments SET attendance=?,arrival_time=?,attendance_note=?,marked_by=?,marked_at=?,revision=revision+1 WHERE id=?',[input.attendance,arrival,reason,userId,Date.now(),a.id]);
 await auditChange(tx,userId,'training.attendance_recorded',a.id,reason,{training_id:id,facilitator_id:f.id,before:a.attendance,after:input.attendance,arrival_time:arrival});
 }
});}
export async function personalTrainings(db,userId){const user=await loadUser(db,userId);if(!user?.facilitator_id||user.must_change)throw new FormError('Sign in and change your temporary password before viewing training.',403);return db.all(`SELECT t.*,a.id AS assignment_id,a.state AS assignment_state,a.attendance,a.arrival_time,a.attendance_note,a.marked_at FROM gmf_training_assignments a JOIN gmf_trainings t ON ${sqlTrainingJoin(db)} WHERE a.facilitator_id=? ORDER BY t.session_date DESC,t.starts_at DESC`,[user.facilitator_id]);}
export async function facilitatorTrainingHistory(db,user,id){const f=(await db.all(registrySelect+' WHERE f.id=?',[id]))[0];if(!f||!can(user,'trainings.view',f))throw new FormError('Facilitator training unavailable.',404);const rows=await db.all(`SELECT t.*,a.state AS assignment_state,a.attendance,a.arrival_time,a.attendance_note FROM gmf_training_assignments a JOIN gmf_trainings t ON ${sqlTrainingJoin(db)} WHERE a.facilitator_id=? ORDER BY t.session_date DESC`,[id]);return {f,rows:rows.map(row=>({...row,attendance_note:can(user,'trainings.manage',f)?row.attendance_note:'Restricted'}))};}
