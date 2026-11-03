import {randomUUID,randomBytes} from 'node:crypto';
import {FormError,fields,validateStep} from './registration-fields.js';
import {can,loadUser} from './policies.js';
import {facilitator,registrySelect} from './registry.js';
import {policyLock} from './registration-services.js';
import {hashPassword} from './security.js';
import {authorization,cardState,hash} from './cards.js';
import {auditChange} from './administration.js';
export async function provisionFacilitatorAccount(db,actorId,id,input){
 const password=typeof input.password==='string'&&input.password?input.password:'Gm1!'+randomBytes(18).toString('base64url');
 if(!input.password&&input.confirm_password)throw new FormError('Enter both temporary password fields or leave both blank.');
 if(input.password&&input.password!==input.confirm_password)throw new FormError('Temporary passwords must match.');
 let encoded;try{encoded=await hashPassword(password);}catch{throw new FormError('Use a temporary password of 12–256 characters.');}
 return db.transaction(async tx=>{
 await policyLock(tx);const actor=await loadUser(tx,actorId);if(!can(actor,'accounts.manage'))throw new FormError('Only an account administrator can allocate facilitator logins.',403);
 const f=await facilitator(tx,id,actor,'accounts.manage');if(Number(input.revision)!==f.revision)throw new FormError('Facilitator changed. Reload before allocating login details.',409);
 if(await authorization(tx,f)!=='ACTIVE')throw new FormError('Allocate logins only to active approved facilitators.');
 const reason=typeof input.reason==='string'?input.reason.trim():'';if(!reason||reason.length>2000)throw new FormError('Provide an allocation or reset reason within 2,000 characters.');
 let account=(await tx.all(`SELECT u.id,u.username,u.active,COALESCE(m.revision,1) AS revision FROM gmf_facilitator_accounts fa JOIN gmf_users u ON ${db.dialect==='mysql'?'CAST(u.id AS BINARY)=CAST(fa.user_id AS BINARY)':'u.id=fa.user_id'} LEFT JOIN gmf_account_meta m ON m.id=u.id WHERE fa.facilitator_id=?`,[f.id]))[0];
 if(input.action==='create'){
 if(account)throw new FormError('This facilitator already has a login. Use Reset temporary password.',409);
 const username=typeof input.username==='string'?input.username.trim().toLowerCase():'';const email=typeof input.email==='string'?input.email.trim().toLowerCase():'';
 if(!/^[a-z0-9_.-]{3,150}$/.test(username)||email&&(!/^\S+@\S+\.\S+$/.test(email)||email.length>254))throw new FormError('Enter a valid username and email.');
 const userId=randomUUID(),accountEmail=email||userId+'@no-email.invalid';
 if((await tx.all('SELECT id FROM gmf_users WHERE username=? OR email=?',[username,accountEmail])).length)throw new FormError('That username or email already belongs to an account. Choose another username/email; existing staff accounts cannot be linked.');
 await tx.run('INSERT INTO gmf_users(id,username,email,password_hash) VALUES (?,?,?,?)',[userId,username,accountEmail,encoded]);
 await tx.run('INSERT INTO gmf_account_meta(id,must_change) VALUES (?,1)',[userId]);await tx.run('INSERT INTO gmf_facilitator_accounts(user_id,facilitator_id) VALUES (?,?)',[userId,f.id]);account={id:userId,username};
 }else if(input.action==='reset'){
 if(!account||!account.active)throw new FormError('An active facilitator account is required.');
 if(account.revision!==Number(input.account_revision))throw new FormError('Account changed. Reload before resetting the temporary password.',409);
 await tx.run('UPDATE gmf_users SET password_hash=? WHERE id=?',[encoded,account.id]);await tx.run('UPDATE gmf_account_meta SET must_change=1,revision=revision+1 WHERE id=?',[account.id]);
 for(const session of await tx.all('SELECT id,payload FROM gmf_sessions')){let saved;try{saved=JSON.parse(session.payload);}catch{continue;}if(saved.userId===account.id)await tx.run('DELETE FROM gmf_sessions WHERE id=?',[session.id]);}
 }else throw new FormError('Choose create or reset.');
 await auditChange(tx,actorId,'facilitator.login_'+input.action,f.id,reason,{user_id:account.id,username:account.username,must_change:true});
 return {username:account.username,password,name:f.full_name,number:f.number};
 });
}
export async function ownFacilitator(db,userId){
 const user=await loadUser(db,userId);if(!user?.facilitator_id)throw new FormError('Facilitator profile unavailable.',403);if(user.must_change)throw new FormError('Change the temporary password before accessing your profile.',403);
 const f=(await db.all(registrySelect+' WHERE f.id=?',[user.facilitator_id]))[0];if(!f)throw new FormError('Facilitator profile unavailable.',404);
 const application=(await db.all('SELECT number,payload,revision FROM gmf_applications WHERE id=?',[f.application_id]))[0];
 return {user,f,application:{...application,data:JSON.parse(application.payload)},fields};
}
export async function ownCard(db,cfg,userId,format='pdf'){
 if(!['pdf','print_pdf'].includes(format))throw new FormError('Choose a valid card format.');
 const {f}=await ownFacilitator(db,userId);const card=(await db.all("SELECT * FROM gmf_cards WHERE facilitator_id=? AND status='ISSUED' ORDER BY version DESC LIMIT 1",[f.id]))[0];
 if(!card||await cardState(db,card,f,cfg)!=='CURRENT')throw new FormError('A current ID card is unavailable. Please contact the administrator.',404);
 const bytes=Buffer.from(card[format],'base64');if(hash(bytes)!==card[format==='pdf'?'pdf_hash':'print_hash'])throw new FormError('Card integrity check failed. Contact the administrator.');
 return {card,bytes};
}

export async function updateOwnProfile(db,userId,input){
 return db.transaction(async tx=>{
 await policyLock(tx);
 const {f,application}=await ownFacilitator(tx,userId);
 if(await authorization(tx,f)!=='ACTIVE')throw new FormError('Only active approved facilitators can update their profile.',403);
 if(application.revision!==Number(input.revision))throw new FormError('Your profile changed. Reload before saving.',409);
 if((await tx.all("SELECT id FROM gmf_approved_corrections WHERE application_id=? AND state IN ('OPEN','SUBMITTED')",[f.application_id])).length)throw new FormError('An administrator correction is pending. Complete that correction before editing your profile.',409);
 const allowed=new Set(['csrf','revision',...fields[3].map(f=>f.name),...fields[4].map(f=>f.name),'public_mobile','public_email','public_social']);
 if(Object.keys(input).some(key=>!allowed.has(key)))throw new FormError('Only professional details, equipment, social links and public display consent can be changed here.');
 const data=application.data,before={3:data[3],4:data[4],consent:data.consent};
 const professional=await validateStep(tx,3,input),equipment=await validateStep(tx,4,input);
 const consent={...(data.consent||{})};
 for(const key of ['public_mobile','public_email','public_social']){
 if(input[key]!==undefined&&input[key]!=='on')throw new FormError('Choose valid public display consent.');
 consent[key]=input[key]==='on';
 }
 consent.public_updated_at=Date.now();
 data[3]=professional;data[4]=equipment;data.consent=consent;
 await tx.run('UPDATE gmf_applications SET payload=?,revision=revision+1 WHERE id=?',[JSON.stringify(data),f.application_id]);
 await auditChange(tx,userId,'facilitator.profile_updated',f.id,'Facilitator updated permitted personal profile fields.',{before,after:{3:professional,4:equipment,consent}});
 });
}
